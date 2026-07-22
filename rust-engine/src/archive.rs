//! Strict reader for the `DD1.DAT` resource archive.

use crate::error::{EngineError, Result, u16_le, u32_le};
use std::fs;
use std::path::Path;

const RECORD_SIZE: usize = 24;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ArchiveEntry {
    pub index: usize,
    pub name: String,
    pub extension: String,
    pub compressed: bool,
    pub offset: usize,
    pub expanded_size: usize,
    pub stored_size: usize,
}

impl ArchiveEntry {
    pub fn filename(&self) -> String {
        if self.extension.is_empty() {
            self.name.clone()
        } else {
            format!("{}.{}", self.name, self.extension)
        }
    }
}

#[derive(Clone, Debug)]
pub struct Archive {
    data: Vec<u8>,
    entries: Vec<ArchiveEntry>,
}

impl Archive {
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        Self::from_bytes(fs::read(path)?)
    }

    pub fn from_bytes(data: Vec<u8>) -> Result<Self> {
        let count = u16_le(&data, 0, "DD1.DAT")? as usize;
        let directory_end = 2usize
            .checked_add(
                count
                    .checked_mul(RECORD_SIZE)
                    .ok_or_else(|| EngineError::format("DD1.DAT", "directory size overflow"))?,
            )
            .ok_or_else(|| EngineError::format("DD1.DAT", "directory size overflow"))?;
        if directory_end > data.len() {
            return Err(EngineError::format("DD1.DAT", "directory extends past EOF"));
        }

        let mut entries = Vec::with_capacity(count);
        let mut expected_offset = directory_end;
        for index in 0..count {
            let base = 2 + index * RECORD_SIZE;
            let context = format!("DD1.DAT entry {index}");
            let name = decode_ascii_field(&data[base..base + 8], &context)?;
            let marker = data[base + 8];
            let extension = decode_ascii_field(&data[base + 9..base + 12], &context)?;
            let offset = u32_le(&data, base + 12, &context)? as usize;
            let expanded_size = u32_le(&data, base + 16, &context)? as usize;
            let stored_size = u32_le(&data, base + 20, &context)? as usize;
            if name.is_empty() {
                return Err(EngineError::format(context, "empty member name"));
            }
            if marker > 1 {
                return Err(EngineError::format(
                    context,
                    format!("invalid marker {marker:#x}"),
                ));
            }
            if offset != expected_offset {
                return Err(EngineError::format(
                    context,
                    format!("payload starts at {offset:#x}, expected {expected_offset:#x}"),
                ));
            }
            if stored_size < 2 {
                return Err(EngineError::format(
                    context,
                    "payload is shorter than GC magic",
                ));
            }
            let end = offset
                .checked_add(stored_size)
                .ok_or_else(|| EngineError::format(&context, "payload offset overflow"))?;
            if end > data.len() {
                return Err(EngineError::format(context, "payload extends past EOF"));
            }
            if data.get(offset..offset + 2) != Some(b"GC") {
                return Err(EngineError::format(context, "missing GC payload magic"));
            }
            if marker == 0 && stored_size != expanded_size + 2 {
                return Err(EngineError::format(context, "raw member size mismatch"));
            }
            entries.push(ArchiveEntry {
                index,
                name,
                extension,
                compressed: marker == 1,
                offset,
                expanded_size,
                stored_size,
            });
            expected_offset = end;
        }
        if expected_offset != data.len() {
            return Err(EngineError::format(
                "DD1.DAT",
                format!("{} trailing bytes", data.len() - expected_offset),
            ));
        }
        Ok(Self { data, entries })
    }

    pub fn entries(&self) -> &[ArchiveEntry] {
        &self.entries
    }

    pub fn find(&self, filename: &str) -> Option<&ArchiveEntry> {
        self.entries
            .iter()
            .find(|entry| entry.filename().eq_ignore_ascii_case(filename))
    }

    pub fn matching(&self, filename: &str) -> impl Iterator<Item = &ArchiveEntry> {
        self.entries
            .iter()
            .filter(move |entry| entry.filename().eq_ignore_ascii_case(filename))
    }

    pub fn read(&self, filename: &str) -> Result<Vec<u8>> {
        let entry = self
            .find(filename)
            .ok_or_else(|| EngineError::MissingResource(filename.to_owned()))?;
        self.extract(entry)
    }

    pub fn extract(&self, entry: &ArchiveEntry) -> Result<Vec<u8>> {
        let start = entry.offset + 2;
        let end = entry.offset + entry.stored_size;
        let body = &self.data[start..end];
        let output = if entry.compressed {
            decode_dictionary(body, entry.expanded_size, &entry.filename())?
        } else {
            body.to_vec()
        };
        if output.len() != entry.expanded_size {
            return Err(EngineError::format(
                entry.filename(),
                format!(
                    "expanded to {}, expected {}",
                    output.len(),
                    entry.expanded_size
                ),
            ));
        }
        Ok(output)
    }
}

fn decode_ascii_field(raw: &[u8], context: &str) -> Result<String> {
    let end = raw.iter().position(|&byte| byte == 0).unwrap_or(raw.len());
    if end < raw.len() && raw[end + 1..].iter().any(|&byte| byte != 0) {
        return Err(EngineError::format(
            context,
            "nonzero directory-field padding",
        ));
    }
    if !raw[..end].is_ascii() {
        return Err(EngineError::format(context, "non-ASCII directory field"));
    }
    Ok(String::from_utf8(raw[..end].to_vec()).expect("ASCII is UTF-8"))
}

fn decode_dictionary(source: &[u8], expected_size: usize, context: &str) -> Result<Vec<u8>> {
    let mut position = 0usize;
    let mut output = Vec::with_capacity(expected_size);
    let mut prefixes = vec![usize::MAX; 0x1001];
    let mut suffixes = vec![0u8; 0x1001];
    for (value, suffix) in suffixes.iter_mut().enumerate().take(0x100) {
        *suffix = value as u8;
    }

    let read = |position: &mut usize, purpose: &str| -> Result<u8> {
        let value = source.get(*position).copied().ok_or_else(|| {
            EngineError::format(context, format!("truncated compressed stream ({purpose})"))
        })?;
        *position += 1;
        Ok(value)
    };

    while output.len() < expected_size {
        let first = read(&mut position, "initial literal")?;
        prefixes[0x100] = first as usize;
        output.push(first);
        let mut next_code = 0x101usize;
        let mut plane_bytes = Vec::new();
        let mut plane_bit = 8usize;

        while next_code < 0x1001 && output.len() < expected_size {
            if plane_bit == 8 {
                let mut plane_count = 0;
                let mut code_limit = 0x100usize;
                while next_code > code_limit {
                    plane_count += 1;
                    code_limit <<= 1;
                }
                plane_bytes.clear();
                for _ in 0..plane_count {
                    plane_bytes.push(read(&mut position, "high-bit plane")?);
                }
                plane_bit = 0;
            }
            let mut code = read(&mut position, "code low byte")? as usize;
            for (bit, plane) in plane_bytes.iter_mut().enumerate() {
                code |= ((*plane & 1) as usize) << (8 + bit);
                *plane >>= 1;
            }
            plane_bit += 1;
            if code >= next_code {
                return Err(EngineError::format(
                    context,
                    format!("undefined dictionary code {code:#x}"),
                ));
            }
            prefixes[next_code] = code;
            let mut chain = Vec::new();
            let mut cursor = code;
            while prefixes[cursor] != usize::MAX {
                chain.push(cursor);
                cursor = prefixes[cursor];
                if chain.len() > 0x1000 {
                    return Err(EngineError::format(context, "cyclic dictionary phrase"));
                }
            }
            let first_character = suffixes[cursor];
            suffixes[next_code - 1] = first_character;
            output.push(first_character);
            for &item in chain.iter().rev() {
                output.push(suffixes[item]);
            }
            if output.len() > expected_size {
                return Err(EngineError::format(context, "dictionary output overflow"));
            }
            next_code += 1;
        }
    }
    if position != source.len() {
        return Err(EngineError::format(
            context,
            format!("{} trailing compressed bytes", source.len() - position),
        ));
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_short_archive() {
        assert!(Archive::from_bytes(vec![0]).is_err());
    }

    #[test]
    fn reads_minimal_raw_archive() {
        let mut data = vec![0; 26];
        data[0..2].copy_from_slice(&1u16.to_le_bytes());
        data[2..5].copy_from_slice(b"ONE");
        data[10] = 0;
        data[11..14].copy_from_slice(b"BIN");
        data[14..18].copy_from_slice(&26u32.to_le_bytes());
        data[18..22].copy_from_slice(&3u32.to_le_bytes());
        data[22..26].copy_from_slice(&5u32.to_le_bytes());
        data.extend_from_slice(b"GCabc");
        let archive = Archive::from_bytes(data).unwrap();
        assert_eq!(archive.read("one.bin").unwrap(), b"abc");
    }
}
