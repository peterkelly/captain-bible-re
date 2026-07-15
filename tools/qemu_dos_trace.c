#include <qemu-plugin.h>

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

struct register_handles {
    struct qemu_plugin_register *eax;
    struct qemu_plugin_register *ebx;
    struct qemu_plugin_register *ecx;
    struct qemu_plugin_register *edx;
    struct qemu_plugin_register *esi;
    struct qemu_plugin_register *edi;
    struct qemu_plugin_register *eip;
    struct qemu_plugin_register *eflags;
    struct qemu_plugin_register *cs;
    struct qemu_plugin_register *ds;
    struct qemu_plugin_register *es;
};

struct pending_call {
    bool active;
    uint8_t vector;
    uint16_t ax;
    uint64_t sequence;
    uint16_t cs;
    uint16_t ip;
};

static struct register_handles registers;
static struct pending_call pending;
static GArray *register_descriptors;
static GHashTable *return_addresses;
static FILE *trace_file;
static GMutex trace_lock;
static uint64_t call_count;
static uint64_t dos_call_count;
static uint64_t driver_call_count;
static bool have_eax;
static bool have_cs_filter;
static uint16_t cs_filter;
static bool have_start_filter;
static uint16_t start_ip;
static bool tracing_active;

static uint64_t read_register_handle(struct qemu_plugin_register *handle)
{
    GByteArray *bytes;
    uint64_t value = 0;
    size_t count;
    size_t index;

    bytes = g_byte_array_new();
    if (!qemu_plugin_read_register(handle, bytes)) {
        g_byte_array_free(bytes, true);
        return 0;
    }

    count = MIN(bytes->len, sizeof(value));
    for (index = 0; index < count; ++index) {
        value |= (uint64_t)bytes->data[index] << (index * 8);
    }
    g_byte_array_free(bytes, true);
    return value;
}

static uint64_t read_register(struct qemu_plugin_register *handle)
{
    if (handle == NULL) {
        return 0;
    }
    return read_register_handle(handle);
}

static void append_escaped(char *output, size_t output_size,
                           const uint8_t *input, size_t input_size,
                           uint8_t terminator)
{
    static const char hex[] = "0123456789ABCDEF";
    size_t input_index;
    size_t output_index = 0;

    if (output_size == 0) {
        return;
    }

    for (input_index = 0; input_index < input_size; ++input_index) {
        uint8_t byte = input[input_index];

        if (byte == terminator) {
            break;
        }
        if (byte >= 0x20 && byte <= 0x7e && byte != '\\' && byte != '"') {
            if (output_index + 1 >= output_size) {
                break;
            }
            output[output_index++] = (char)byte;
        } else if (byte == '\\' || byte == '"') {
            if (output_index + 2 >= output_size) {
                break;
            }
            output[output_index++] = '\\';
            output[output_index++] = (char)byte;
        } else {
            if (output_index + 4 >= output_size) {
                break;
            }
            output[output_index++] = '\\';
            output[output_index++] = 'x';
            output[output_index++] = hex[byte >> 4];
            output[output_index++] = hex[byte & 0x0f];
        }
    }
    output[output_index] = '\0';
}

static bool read_guest_string(uint16_t segment, uint16_t offset,
                              uint8_t terminator, char *output,
                              size_t output_size)
{
    GByteArray *bytes;
    uint64_t physical = (uint64_t)segment * 16 + offset;
    enum qemu_plugin_hwaddr_operation_result result;

    bytes = g_byte_array_sized_new(160);
    result = qemu_plugin_read_memory_hwaddr(physical, bytes, 160);
    if (result != QEMU_PLUGIN_HWADDR_OPERATION_OK) {
        g_byte_array_free(bytes, true);
        return false;
    }
    append_escaped(output, output_size, bytes->data, bytes->len, terminator);
    g_byte_array_free(bytes, true);
    return true;
}

static const char *dos_call_name(uint8_t function)
{
    switch (function) {
    case 0x09: return "PRINT_STRING";
    case 0x0e: return "SET_DRIVE";
    case 0x19: return "GET_DRIVE";
    case 0x1a: return "SET_DTA";
    case 0x25: return "SET_VECTOR";
    case 0x2a: return "GET_DATE";
    case 0x2c: return "GET_TIME";
    case 0x2f: return "GET_DTA";
    case 0x30: return "GET_DOS_VERSION";
    case 0x35: return "GET_VECTOR";
    case 0x39: return "MKDIR";
    case 0x3a: return "RMDIR";
    case 0x3b: return "CHDIR";
    case 0x3c: return "CREATE";
    case 0x3d: return "OPEN";
    case 0x3e: return "CLOSE";
    case 0x3f: return "READ";
    case 0x40: return "WRITE";
    case 0x41: return "DELETE";
    case 0x42: return "SEEK";
    case 0x43: return "ATTR";
    case 0x44: return "IOCTL";
    case 0x45: return "DUP";
    case 0x46: return "DUP2";
    case 0x47: return "GETCWD";
    case 0x48: return "ALLOCATE";
    case 0x49: return "FREE";
    case 0x4a: return "RESIZE";
    case 0x4b: return "EXEC";
    case 0x4c: return "EXIT";
    case 0x4e: return "FIND_FIRST";
    case 0x4f: return "FIND_NEXT";
    case 0x56: return "RENAME";
    case 0x57: return "FILE_TIME";
    case 0x5b: return "CREATE_NEW";
    case 0x6c: return "EXT_OPEN";
    case 0xff: return "UNKNOWN";
    default: return "OTHER";
    }
}

static bool dx_is_asciiz_path(uint8_t function)
{
    switch (function) {
    case 0x39:
    case 0x3a:
    case 0x3b:
    case 0x3c:
    case 0x3d:
    case 0x41:
    case 0x43:
    case 0x4b:
    case 0x4e:
    case 0x56:
    case 0x5b:
        return true;
    default:
        return false;
    }
}

static bool infer_interrupt_ax(uint16_t cs, uint16_t ip,
                               uint16_t *ax)
{
    const size_t lookbehind = MIN((size_t)ip, 48);
    const uint64_t physical = (uint64_t)cs * 16 + ip - lookbehind;
    GByteArray *bytes;
    enum qemu_plugin_hwaddr_operation_result result;
    size_t end;

    if (lookbehind < 2) {
        return false;
    }

    bytes = g_byte_array_sized_new(lookbehind);
    result = qemu_plugin_read_memory_hwaddr(physical, bytes, lookbehind);
    if (result != QEMU_PLUGIN_HWADDR_OPERATION_OK) {
        g_byte_array_free(bytes, true);
        return false;
    }

    end = bytes->len;
    while (end >= 2) {
        if (bytes->data[end - 2] == 0xb4) {
            *ax = (uint16_t)bytes->data[end - 1] << 8;
            g_byte_array_free(bytes, true);
            return true;
        }
        if (end >= 3 && bytes->data[end - 3] == 0xb8) {
            *ax = (uint16_t)bytes->data[end - 2] |
                  (uint16_t)bytes->data[end - 1] << 8;
            g_byte_array_free(bytes, true);
            return true;
        }
        --end;
    }

    g_byte_array_free(bytes, true);
    return false;
}

static void trace_interrupt(unsigned int vcpu_index, void *userdata)
{
    uint8_t vector = (uint8_t)GPOINTER_TO_UINT(userdata);
    uint16_t ax = have_eax ?
                  (uint16_t)read_register_handle(registers.eax) : 0xffff;
    uint16_t bx = (uint16_t)read_register(registers.ebx);
    uint16_t cx = (uint16_t)read_register(registers.ecx);
    uint16_t dx = (uint16_t)read_register(registers.edx);
    uint16_t si = (uint16_t)read_register(registers.esi);
    uint16_t di = (uint16_t)read_register(registers.edi);
    uint16_t cs = (uint16_t)read_register(registers.cs);
    uint16_t ds = (uint16_t)read_register(registers.ds);
    uint16_t es = (uint16_t)read_register(registers.es);
    uint16_t ip = (uint16_t)read_register(registers.eip);
    uint8_t function;
    char first[324] = "";
    char second[324] = "";

    (void)vcpu_index;

    if (!tracing_active || (have_cs_filter && cs != cs_filter)) {
        return;
    }
    if (!have_eax && !infer_interrupt_ax(cs, ip, &ax)) {
        ax = 0xffff;
    }
    function = (uint8_t)(ax >> 8);

    if (vector == 0x21 && dx_is_asciiz_path(function)) {
        read_guest_string(ds, dx, 0, first, sizeof(first));
    } else if (vector == 0x21 && function == 0x09) {
        read_guest_string(ds, dx, '$', first, sizeof(first));
    } else if (vector == 0x21 && function == 0x6c) {
        read_guest_string(ds, si, 0, first, sizeof(first));
    }
    if (vector == 0x21 && function == 0x56) {
        read_guest_string(es, di, 0, second, sizeof(second));
    }

    g_mutex_lock(&trace_lock);
    ++call_count;
    if (vector == 0x21) {
        ++dos_call_count;
    } else if (vector == 0x66) {
        ++driver_call_count;
    }
    pending.active = true;
    pending.vector = vector;
    pending.ax = ax;
    pending.sequence = call_count;
    pending.cs = cs;
    pending.ip = ip;
    fprintf(trace_file,
            "CALL %06" PRIu64 " pc=%04X:%04X linear=%05" PRIX64 " "
            "int=%02X AX=%04X ",
            call_count, cs, ip, (uint64_t)cs * 16 + ip, vector, ax);
    if (vector == 0x21) {
        fprintf(trace_file, "fn=%02X %-15s ",
                function, dos_call_name(function));
    } else {
        fprintf(trace_file, "service=%04X ", ax);
    }
    fprintf(trace_file,
            "BX=%04X CX=%04X DX=%04X SI=%04X DI=%04X "
            "DS=%04X ES=%04X",
            bx, cx, dx, si, di, ds, es);
    if (first[0] != '\0') {
        fprintf(trace_file, " arg=\"%s\"", first);
    }
    if (second[0] != '\0') {
        fprintf(trace_file, " arg2=\"%s\"", second);
    }
    fputc('\n', trace_file);
    fflush(trace_file);
    g_mutex_unlock(&trace_lock);
}

static void trace_return(unsigned int vcpu_index, void *userdata)
{
    uint16_t ax;
    uint16_t bx;
    uint16_t cx;
    uint16_t dx;
    uint16_t si;
    uint16_t di;
    uint16_t ds;
    uint16_t es;
    uint16_t cs;
    uint16_t ip;
    uint32_t eflags;
    char result[324] = "";

    (void)vcpu_index;
    (void)userdata;

    if (!pending.active) {
        return;
    }

    ax = have_eax ? (uint16_t)read_register_handle(registers.eax) : 0xffff;
    bx = (uint16_t)read_register(registers.ebx);
    cx = (uint16_t)read_register(registers.ecx);
    dx = (uint16_t)read_register(registers.edx);
    si = (uint16_t)read_register(registers.esi);
    di = (uint16_t)read_register(registers.edi);
    ds = (uint16_t)read_register(registers.ds);
    es = (uint16_t)read_register(registers.es);
    cs = (uint16_t)read_register(registers.cs);
    ip = (uint16_t)read_register(registers.eip);
    eflags = (uint32_t)read_register(registers.eflags);
    if (pending.vector == 0x66 && pending.ax == 0x068c) {
        read_guest_string(bx, cx, 0, result, sizeof(result));
    }

    g_mutex_lock(&trace_lock);
    fprintf(trace_file,
            "RET  %06" PRIu64 " pc=%04X:%04X from=%04X:%04X "
            "int=%02X AX=%04X BX=%04X CX=%04X DX=%04X "
            "SI=%04X DI=%04X DS=%04X ES=%04X CF=%u",
            pending.sequence, cs, ip, pending.cs, pending.ip,
            pending.vector, ax, bx, cx, dx, si, di, ds, es, eflags & 1);
    if (result[0] != '\0') {
        fprintf(trace_file, " result=\"%s\"", result);
    }
    fputc('\n', trace_file);
    fflush(trace_file);
    pending.active = false;
    g_mutex_unlock(&trace_lock);
}

static void activate_trace(unsigned int vcpu_index, void *userdata)
{
    (void)vcpu_index;
    (void)userdata;

    if (tracing_active) {
        return;
    }
    g_mutex_lock(&trace_lock);
    tracing_active = true;
    fprintf(trace_file, "# tracing activated at %04X:%04X\n",
            cs_filter, start_ip);
    fflush(trace_file);
    g_mutex_unlock(&trace_lock);
}

static void translate_block(qemu_plugin_id_t id, struct qemu_plugin_tb *tb)
{
    size_t instruction_count = qemu_plugin_tb_n_insns(tb);
    bool activate_on_entry = false;
    uint8_t trace_vector_on_entry = 0;
    bool trace_return_on_entry = false;
    size_t index;

    (void)id;

    for (index = 0; index < instruction_count; ++index) {
        struct qemu_plugin_insn *instruction;
        uint8_t bytes[2];
        uint64_t address;
        size_t size;

        instruction = qemu_plugin_tb_get_insn(tb, index);
        address = qemu_plugin_insn_vaddr(instruction);
        size = qemu_plugin_insn_size(instruction);

        if (g_hash_table_contains(return_addresses,
                                  GSIZE_TO_POINTER((gsize)address))) {
            trace_return_on_entry = true;
        }

        if (size == 2 && qemu_plugin_insn_data(instruction, bytes, 2) == 2 &&
            bytes[0] == 0xcd &&
            (bytes[1] == 0x21 || bytes[1] == 0x66)) {
            g_hash_table_add(return_addresses,
                             GSIZE_TO_POINTER((gsize)(address + size)));
            trace_vector_on_entry = bytes[1];
        }
        if (have_start_filter &&
            address == (uint64_t)cs_filter * 16 + start_ip) {
            activate_on_entry = true;
        }
    }

    /* Traced runs use one instruction per translation block. Register reads
       here therefore describe the state before the selected instruction. */
    if (activate_on_entry) {
        qemu_plugin_register_vcpu_tb_exec_cb(
            tb, activate_trace, QEMU_PLUGIN_CB_NO_REGS, NULL);
    }
    if (trace_vector_on_entry != 0) {
        qemu_plugin_register_vcpu_tb_exec_cb(
            tb, trace_interrupt, QEMU_PLUGIN_CB_R_REGS,
            GUINT_TO_POINTER(trace_vector_on_entry));
    }
    if (trace_return_on_entry) {
        qemu_plugin_register_vcpu_tb_exec_cb(
            tb, trace_return, QEMU_PLUGIN_CB_R_REGS, NULL);
    }
}

static void initialize_vcpu(qemu_plugin_id_t id, unsigned int vcpu_index)
{
    GArray *descriptors = qemu_plugin_get_registers();
    guint index;

    (void)id;

    for (index = 0; index < descriptors->len; ++index) {
        qemu_plugin_reg_descriptor *descriptor;
        const char *name;
        struct qemu_plugin_register *handle;

        descriptor = &g_array_index(descriptors,
                                    qemu_plugin_reg_descriptor, index);
        name = descriptor->name;
        handle = descriptor->handle;
        if (g_ascii_strcasecmp(name, "eax") == 0) {
            registers.eax = handle;
            have_eax = true;
        } else if (g_ascii_strcasecmp(name, "ebx") == 0) {
            registers.ebx = handle;
        }
        else if (g_ascii_strcasecmp(name, "ecx") == 0) registers.ecx = handle;
        else if (g_ascii_strcasecmp(name, "edx") == 0) registers.edx = handle;
        else if (g_ascii_strcasecmp(name, "esi") == 0) registers.esi = handle;
        else if (g_ascii_strcasecmp(name, "edi") == 0) registers.edi = handle;
        else if (g_ascii_strcasecmp(name, "eip") == 0) registers.eip = handle;
        else if (g_ascii_strcasecmp(name, "eflags") == 0) {
            registers.eflags = handle;
        } else if (g_ascii_strcasecmp(name, "cs") == 0) registers.cs = handle;
        else if (g_ascii_strcasecmp(name, "ds") == 0) registers.ds = handle;
        else if (g_ascii_strcasecmp(name, "es") == 0) registers.es = handle;
    }

    g_mutex_lock(&trace_lock);
    fprintf(trace_file, "# vCPU %u registers:", vcpu_index);
    for (index = 0; index < descriptors->len; ++index) {
        qemu_plugin_reg_descriptor *descriptor;

        descriptor = &g_array_index(descriptors,
                                    qemu_plugin_reg_descriptor, index);
        fprintf(trace_file, " %s", descriptor->name);
    }
    fputc('\n', trace_file);
    if (have_eax) {
        fputs("# AX is captured from live EAX at interrupt entry and return\n",
              trace_file);
    } else {
        fputs("# input AX is inferred from the nearest preceding MOV AH/AX; "
              "return AX is unavailable\n", trace_file);
    }
    fflush(trace_file);
    g_mutex_unlock(&trace_lock);
    register_descriptors = descriptors;
}

static void finish_trace(qemu_plugin_id_t id, void *userdata)
{
    (void)id;
    (void)userdata;

    g_mutex_lock(&trace_lock);
    fprintf(trace_file,
            "# captured calls: %" PRIu64 " (DOS=%" PRIu64
            ", driver=%" PRIu64 ")\n",
            call_count, dos_call_count, driver_call_count);
    fclose(trace_file);
    trace_file = NULL;
    g_mutex_unlock(&trace_lock);
    g_array_free(register_descriptors, true);
    g_hash_table_destroy(return_addresses);
    g_mutex_clear(&trace_lock);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                           const qemu_info_t *info,
                                           int argc, char **argv)
{
    const char *log_path = "qemu-dos-trace.log";
    int index;

    if (!info->system_emulation || strcmp(info->target_name, "i386") != 0) {
        fprintf(stderr, "qemu_dos_trace requires i386 system emulation\n");
        return -1;
    }

    for (index = 0; index < argc; ++index) {
        if (g_str_has_prefix(argv[index], "log=")) {
            log_path = argv[index] + 4;
        } else if (g_str_has_prefix(argv[index], "cs=")) {
            char *end = NULL;
            uint64_t value;

            errno = 0;
            value = g_ascii_strtoull(argv[index] + 3, &end, 0);
            if (errno != 0 || end == argv[index] + 3 || *end != '\0' ||
                value > UINT16_MAX) {
                fprintf(stderr, "invalid qemu_dos_trace cs value: %s\n",
                        argv[index] + 3);
                return -1;
            }
            have_cs_filter = true;
            cs_filter = (uint16_t)value;
        } else if (g_str_has_prefix(argv[index], "start=")) {
            char *end = NULL;
            uint64_t value;

            errno = 0;
            value = g_ascii_strtoull(argv[index] + 6, &end, 0);
            if (errno != 0 || end == argv[index] + 6 || *end != '\0' ||
                value > UINT16_MAX) {
                fprintf(stderr, "invalid qemu_dos_trace start value: %s\n",
                        argv[index] + 6);
                return -1;
            }
            have_start_filter = true;
            start_ip = (uint16_t)value;
        } else {
            fprintf(stderr, "unknown qemu_dos_trace option: %s\n", argv[index]);
            return -1;
        }
    }

    if (have_start_filter && !have_cs_filter) {
        fprintf(stderr, "qemu_dos_trace start requires a cs value\n");
        return -1;
    }
    tracing_active = !have_start_filter;

    trace_file = fopen(log_path, "w");
    if (trace_file == NULL) {
        fprintf(stderr, "cannot open qemu_dos_trace log %s: %s\n",
                log_path, strerror(errno));
        return -1;
    }

    g_mutex_init(&trace_lock);
    return_addresses = g_hash_table_new(g_direct_hash, g_direct_equal);
    fprintf(trace_file, "# qemu_dos_trace target=%s api=%d..%d",
            info->target_name, info->version.min, info->version.cur);
    if (have_cs_filter) {
        fprintf(trace_file, " cs=%04X", cs_filter);
    }
    if (have_start_filter) {
        fprintf(trace_file, " start=%04X", start_ip);
    }
    fputc('\n', trace_file);
    fflush(trace_file);

    qemu_plugin_register_vcpu_init_cb(id, initialize_vcpu);
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate_block);
    qemu_plugin_register_atexit_cb(id, finish_trace, NULL);
    return 0;
}
