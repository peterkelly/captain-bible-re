//! Bounds-checked decoding for all 145 scene opcodes.

use crate::error::{EngineError, Result};
use crate::text::decode_cp437;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OperandKind {
    Byte,
    Word,
    InlineString,
    StringPointer,
    Record9,
    SignedExtra,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Operand {
    Byte(u8),
    Word(u16),
    String { offset: usize, text: String },
    StringOffset(u16),
    Record9([u8; 9]),
}

impl Operand {
    pub fn byte(&self) -> u8 {
        if let Self::Byte(value) = self {
            *value
        } else {
            panic!("operand is not a byte")
        }
    }
    pub fn word(&self) -> u16 {
        if let Self::Word(value) = self {
            *value
        } else {
            panic!("operand is not a word")
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Instruction {
    pub offset: usize,
    pub end: usize,
    pub opcode: u8,
    pub operands: Vec<Operand>,
}

pub fn decode(data: &[u8], offset: usize) -> Result<Instruction> {
    let opcode = *data
        .get(offset)
        .ok_or_else(|| EngineError::format("BIN", format!("missing opcode at {offset:#x}")))?;
    let schema = schema(opcode).ok_or_else(|| {
        EngineError::format("BIN", format!("invalid opcode {opcode:#x} at {offset:#x}"))
    })?;
    let mut position = offset + 1;
    let mut operands = Vec::with_capacity(schema.len());
    let mut last_signed = 0i16;
    for &kind in schema {
        match kind {
            OperandKind::Byte => {
                let value = *data.get(position).ok_or_else(|| {
                    EngineError::format("BIN", format!("truncated byte at {position:#x}"))
                })?;
                operands.push(Operand::Byte(value));
                position += 1;
            }
            OperandKind::Word => {
                let bytes = data.get(position..position + 2).ok_or_else(|| {
                    EngineError::format("BIN", format!("truncated word at {position:#x}"))
                })?;
                let value = u16::from_le_bytes([bytes[0], bytes[1]]);
                last_signed = value as i16;
                operands.push(Operand::Word(value));
                position += 2;
            }
            OperandKind::InlineString | OperandKind::StringPointer => {
                if kind == OperandKind::StringPointer && data.get(position) == Some(&0xff) {
                    let bytes = data
                        .get(position + 1..position + 3)
                        .ok_or_else(|| EngineError::format("BIN", "truncated string offset"))?;
                    operands.push(Operand::StringOffset(u16::from_le_bytes([
                        bytes[0], bytes[1],
                    ])));
                    position += 3;
                } else {
                    let end = data[position..]
                        .iter()
                        .position(|&byte| byte == 0)
                        .map(|value| position + value)
                        .ok_or_else(|| {
                            EngineError::format(
                                "BIN",
                                format!("unterminated string at {position:#x}"),
                            )
                        })?;
                    operands.push(Operand::String {
                        offset: position,
                        text: decode_cp437(&data[position..end]),
                    });
                    position = end + 1;
                }
            }
            OperandKind::Record9 => {
                let record: [u8; 9] = data
                    .get(position..position + 9)
                    .ok_or_else(|| EngineError::format("BIN", "truncated animation record"))?
                    .try_into()
                    .unwrap();
                operands.push(Operand::Record9(record));
                position += 9;
            }
            OperandKind::SignedExtra => {
                if last_signed < 0 {
                    let bytes = data
                        .get(position..position + 2)
                        .ok_or_else(|| EngineError::format("BIN", "truncated callback target"))?;
                    operands.push(Operand::Word(u16::from_le_bytes([bytes[0], bytes[1]])));
                    position += 2;
                }
            }
        }
    }
    Ok(Instruction {
        offset,
        end: position,
        opcode,
        operands,
    })
}

pub fn string_operand<'a>(program: &'a [u8], operand: &'a Operand) -> Result<String> {
    match operand {
        Operand::String { text, .. } => Ok(text.clone()),
        Operand::StringOffset(offset) => {
            let start = usize::from(*offset);
            let data = program
                .get(start..)
                .ok_or_else(|| EngineError::format("BIN", "string offset is out of range"))?;
            let end = data
                .iter()
                .position(|&byte| byte == 0)
                .ok_or_else(|| EngineError::format("BIN", "unterminated referenced string"))?;
            Ok(decode_cp437(&data[..end]))
        }
        _ => Err(EngineError::format("BIN", "operand is not a string")),
    }
}

const B: OperandKind = OperandKind::Byte;
const H: OperandKind = OperandKind::Word;
const Z: OperandKind = OperandKind::InlineString;
const P: OperandKind = OperandKind::StringPointer;
const R: OperandKind = OperandKind::Record9;
const S: OperandKind = OperandKind::SignedExtra;

pub fn schema(opcode: u8) -> Option<&'static [OperandKind]> {
    Some(match opcode {
        0x01 => &[Z],
        0x02 => &[B, H, H, H],
        0x03 => &[B, B, H, H, B],
        0x04 => &[B, B, H, H, H, B],
        0x05 => &[],
        0x06 => &[H],
        0x07 => &[R],
        0x08 => &[B, B],
        0x09 => &[B],
        0x0a => &[],
        0x0b => &[B, B],
        0x0c => &[B, B, P],
        0x0d => &[Z, Z],
        0x0e => &[],
        0x0f => &[H],
        0x10 => &[B, H, H, P],
        0x11 | 0x12 => &[B, H, S],
        0x13 => &[H],
        0x14 => &[P],
        0x15 => &[B],
        0x16 => &[H, H, H],
        0x17..=0x1a => &[B, H, S],
        0x1b => &[H],
        0x1c | 0x1d => &[B],
        0x1e..=0x21 => &[H, H],
        0x22..=0x29 => &[H, H, H],
        0x2a..=0x31 => &[H, H],
        0x32..=0x34 => &[H],
        0x35 => &[],
        0x36 | 0x37 => &[B],
        0x38 | 0x39 => &[B, H],
        0x3a => &[H, H, H, P],
        0x3b | 0x3c => &[B],
        0x3d => &[H],
        0x3e => &[B, H],
        0x3f | 0x40 => &[B],
        0x41 | 0x42 => &[],
        0x43 => &[B, B, H, H, H, B],
        0x44 => &[H, P],
        0x45 | 0x46 => &[],
        0x47 => &[B],
        0x48 => &[P],
        0x49..=0x4b => &[],
        0x4c => &[B],
        0x4d => &[Z],
        0x4e => &[P],
        0x4f => &[B, B],
        0x50 => &[],
        0x51 => &[B, H, B],
        0x52..=0x54 => &[B],
        0x55 | 0x56 => &[],
        0x57 => &[B, H],
        0x58 | 0x59 => &[],
        0x5a => &[H],
        0x5b => &[B],
        0x5c | 0x5d => &[B, B, B],
        0x5e => &[H],
        0x5f => &[B, B, B],
        0x60 => &[],
        0x61 => &[B],
        0x62..=0x64 => &[H],
        0x65 => &[B, B],
        0x66 => &[B, B, B, B],
        0x67 => &[],
        0x68 => &[H],
        0x69 | 0x6a => &[H, H],
        0x6b => &[B],
        0x6c => &[H, H, H, H],
        0x6d => &[Z],
        0x6e => &[B],
        0x6f | 0x70 => &[],
        0x71 => &[H, H],
        0x72 => &[],
        0x73 | 0x74 => &[B, H],
        0x75 | 0x76 => &[B],
        0x77 => &[],
        0x78 => &[B],
        0x79 => &[],
        0x7a => &[H, H],
        0x7b | 0x7c => &[H],
        0x7d => &[B, H],
        0x7e => &[],
        0x7f => &[H],
        0x80 => &[B, H],
        0x81 => &[H],
        0x82 => &[H, H],
        0x83 => &[H, B, H],
        0x84 => &[H, H],
        0x85 | 0x86 => &[B],
        0x87..=0x89 => &[],
        0x8a => &[B, H],
        0x8b => &[],
        0x8c | 0x8d => &[H],
        0x8e => &[],
        0x8f..=0x91 => &[H, H],
        _ => return None,
    })
}

pub fn code_regions(filename: &str, size: usize) -> Vec<std::ops::Range<usize>> {
    if filename.eq_ignore_ascii_case("CP2.BIN") {
        std::iter::once(0..0x1d55).collect()
    } else if filename.eq_ignore_ascii_case("ROOM3.BIN") {
        vec![0..0x336, 0xc96..0x1754, 0x1768..size]
    } else {
        std::iter::once(0..size).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn has_every_opcode_schema() {
        for opcode in 1..=0x91 {
            assert!(schema(opcode).is_some(), "{opcode:#x}");
        }
    }
    #[test]
    fn signed_callback_reads_extra_target() {
        let command = decode(&[0x11, 3, 0xfe, 0xff, 0x34, 0x12], 0).unwrap();
        assert_eq!(command.end, 6);
    }
}
