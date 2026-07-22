//! Translation indexes and companion gameplay text.

use crate::error::{EngineError, Result, u16_le};

pub const DESCRIPTOR_COUNT: usize = 66;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TextComponent {
    pub tag: u8,
    pub text: String,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct TextDescriptor {
    pub state: u8,
    pub selector: u8,
    pub companion_offset: u16,
    pub companion_span: u16,
    pub citation: String,
    pub verse: String,
    pub components: Vec<TextComponent>,
}

impl TextDescriptor {
    pub fn component(&self, requested: u8) -> Option<&str> {
        let tag = match requested {
            b'*' => b'*',
            0x64 => b'P',
            0 => return None,
            _ => b'L',
        };
        self.components
            .iter()
            .find(|component| component.tag == tag)
            .map(|component| component.text.as_str())
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TextBank {
    pub letter: u8,
    pub descriptors: Vec<TextDescriptor>,
}

impl TextBank {
    pub fn parse(letter: u8, index: &[u8], companion: &[u8], filter_mature: bool) -> Result<Self> {
        let mut records = Vec::new();
        let mut position = 0usize;
        loop {
            let selector = *index
                .get(position)
                .ok_or_else(|| EngineError::format("text index", "missing terminal record"))?;
            let companion_offset = u16_le(index, position + 1, "text index")?;
            position += 3;
            if usize::from(companion_offset) > companion.len() {
                return Err(EngineError::format(
                    "text index",
                    "companion offset exceeds file",
                ));
            }
            if selector == 0 {
                if usize::from(companion_offset) != companion.len() || position != index.len() {
                    return Err(EngineError::format("text index", "invalid terminal record"));
                }
                break;
            }
            let end = index[position..]
                .iter()
                .position(|&byte| byte == 0)
                .map(|value| position + value)
                .ok_or_else(|| EngineError::format("text index", "unterminated citation/verse"))?;
            let joined = decode_cp437(&index[position..end]);
            let (citation, verse) = joined.split_once('|').ok_or_else(|| {
                EngineError::format("text index", "record has no citation separator")
            })?;
            records.push((
                selector,
                companion_offset,
                citation.to_owned(),
                verse.to_owned(),
            ));
            position = end + 1;
        }
        if records.len() > DESCRIPTOR_COUNT {
            return Err(EngineError::format(
                "text index",
                "more than 66 runtime records",
            ));
        }
        let mut descriptors = Vec::with_capacity(records.len());
        for (record_index, (selector, offset, citation, verse)) in records.iter().enumerate() {
            let next = records
                .get(record_index + 1)
                .map(|record| record.1 as usize)
                .unwrap_or(companion.len());
            let start = usize::from(*offset);
            if next < start {
                return Err(EngineError::format(
                    "text index",
                    "companion offsets decrease",
                ));
            }
            let span = next - start;
            if span > u16::MAX as usize {
                return Err(EngineError::format(
                    "text index",
                    "companion span exceeds a word",
                ));
            }
            let components = parse_components(&companion[start..next])?;
            if !filter_mature || *selector < 0xe0 {
                descriptors.push(TextDescriptor {
                    state: 0,
                    selector: *selector,
                    companion_offset: *offset,
                    companion_span: span as u16,
                    citation: citation.clone(),
                    verse: verse.clone(),
                    components,
                });
            }
        }
        Ok(Self {
            letter,
            descriptors,
        })
    }

    pub fn by_selector(&self, selector: u8) -> Option<&TextDescriptor> {
        self.descriptors
            .iter()
            .find(|record| record.selector == selector)
    }

    pub fn by_selector_mut(&mut self, selector: u8) -> Option<&mut TextDescriptor> {
        self.descriptors
            .iter_mut()
            .find(|record| record.selector == selector)
    }
}

const EXPORT_BANK_HEADINGS: [(u8, &str); 8] = [
    (
        b'A',
        "BUILDING A - Round Tubes with Fireballs - Relative Moralist",
    ),
    (b'B', "BUILDING B - Huge Dark Blue - Fearful"),
    (b'C', "BUILDING C - The First Building - Cultist"),
    (b'D', "BUILDING D - Purple Lights - Legalist"),
    (b'E', "BUILDING E - Wall with Platforms - Greedy"),
    (b'F', "BUILDING F - Green and Purple - Drug Abuser"),
    (b'G', "BUILDING G - Caves - New Ager"),
    (b'R', "BUILDING R - In the Unibot"),
];

/// Produce the original command-line study export, including DOS CRLFs,
/// form-feed bank separators, CP437 encoding, and 70-column wrapping.
pub fn export_study(banks: &[TextBank], mask: u8, filter_mature: bool) -> Result<Vec<u8>> {
    let mut output = b"CAPTAIN BIBLE IN DOME OF DARKNESS\r\n\r\n\0\r\n\r\n".to_vec();
    for (bank_index, &(letter, heading)) in EXPORT_BANK_HEADINGS.iter().enumerate() {
        let bank = banks
            .iter()
            .find(|bank| bank.letter == letter)
            .ok_or_else(|| EngineError::format("text export", "required bank is missing"))?;
        if bank_index != 0 {
            output.extend_from_slice(b"\x0c\r\n\r\n");
        }
        output.extend_from_slice(&encode_cp437(heading)?);
        output.extend_from_slice(b"\r\n\r\n");
        for (record_index, record) in bank.descriptors.iter().enumerate() {
            if filter_mature && record.selector >= 0xe0 {
                continue;
            }
            let mut body = Vec::new();
            if mask & 1 != 0 {
                body.extend_from_slice(format!("#{:02}\r\n", record_index + 1).as_bytes());
            }
            for component in &record.components {
                let (bit, label) = match component.tag {
                    b'L' => (2, "CYBER LIE:"),
                    b'P' => (4, "PARAPHRASE:"),
                    b'*' => (8, "CONVERSATION WITH VICTIM:"),
                    b'W' => (16, "WRONG GUESS:"),
                    b'C' => (16, "CORRECT GUESS:"),
                    b'E' => (16, "EXPLANATION OF CORRECT GUESS:"),
                    b'M' => continue,
                    _ => unreachable!(),
                };
                if mask & bit != 0 {
                    body.extend_from_slice(label.as_bytes());
                    body.extend_from_slice(b"\r\n");
                    write_wrapped_export_text(&mut body, &encode_cp437(&component.text)?);
                }
            }
            if mask & 32 != 0 {
                body.extend_from_slice(b"VERSE:\r\n");
                let mut verse = encode_cp437(&record.citation)?;
                verse.extend_from_slice(b" - ");
                verse.extend_from_slice(&encode_cp437(&record.verse)?);
                write_wrapped_export_text(&mut body, &verse);
            }
            if !body.is_empty() {
                output.extend_from_slice(b"\r\n");
                output.extend_from_slice(&body);
            }
        }
    }
    output.extend_from_slice(
        b"\r\n\r\nThis study is copyrighted material as stated in the User Guide.\r\n\
Please respect the rights of the owners of the copyrights.\r\n\0",
    );
    Ok(output)
}

fn write_wrapped_export_text(output: &mut Vec<u8>, text: &[u8]) {
    let mut remaining = text;
    while remaining.len() > 70 {
        let split = remaining[..70]
            .iter()
            .rposition(|&byte| byte == b' ')
            .unwrap_or(70);
        output.extend_from_slice(&remaining[..split]);
        output.extend_from_slice(b"\r\n");
        remaining = &remaining[split..];
        while remaining.first() == Some(&b' ') {
            remaining = &remaining[1..];
        }
    }
    output.extend_from_slice(remaining);
    output.extend_from_slice(b"\r\n");
}

fn parse_components(data: &[u8]) -> Result<Vec<TextComponent>> {
    let mut components = Vec::new();
    let mut position = 0usize;
    while position < data.len() {
        let tag = data[position];
        if !matches!(tag, b'L' | b'P' | b'W' | b'C' | b'E' | b'*' | b'M') {
            return Err(EngineError::format(
                "companion text",
                format!("invalid tag {tag:#x}"),
            ));
        }
        position += 1;
        let end = data[position..]
            .iter()
            .position(|&byte| byte == 0)
            .map(|value| position + value)
            .ok_or_else(|| EngineError::format("companion text", "unterminated component"))?;
        components.push(TextComponent {
            tag,
            text: decode_cp437(&data[position..end]),
        });
        position = end + 1;
    }
    Ok(components)
}

pub fn decode_cp437(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|&byte| {
            if byte < 0x80 {
                byte as char
            } else {
                CP437[(byte - 0x80) as usize]
            }
        })
        .collect()
}

pub fn encode_cp437(text: &str) -> Result<Vec<u8>> {
    text.chars()
        .map(|character| {
            if character as u32 <= 0x7f {
                Ok(character as u8)
            } else {
                CP437
                    .iter()
                    .position(|&item| item == character)
                    .map(|index| index as u8 + 0x80)
                    .ok_or_else(|| {
                        EngineError::format(
                            "CP437",
                            format!("unrepresentable character {character:?}"),
                        )
                    })
            }
        })
        .collect()
}

const CP437: [char; 128] = [
    'Ç', 'ü', 'é', 'â', 'ä', 'à', 'å', 'ç', 'ê', 'ë', 'è', 'ï', 'î', 'ì', 'Ä', 'Å', 'É', 'æ', 'Æ',
    'ô', 'ö', 'ò', 'û', 'ù', 'ÿ', 'Ö', 'Ü', '¢', '£', '¥', '₧', 'ƒ', 'á', 'í', 'ó', 'ú', 'ñ', 'Ñ',
    'ª', 'º', '¿', '⌐', '¬', '½', '¼', '¡', '«', '»', '░', '▒', '▓', '│', '┤', '╡', '╢', '╖', '╕',
    '╣', '║', '╗', '╝', '╜', '╛', '┐', '└', '┴', '┬', '├', '─', '┼', '╞', '╟', '╚', '╔', '╩', '╦',
    '╠', '═', '╬', '╧', '╨', '╤', '╥', '╙', '╘', '╒', '╓', '╫', '╪', '┘', '┌', '█', '▄', '▌', '▐',
    '▀', 'α', 'ß', 'Γ', 'π', 'Σ', 'σ', 'µ', 'τ', 'Φ', 'Θ', 'Ω', 'δ', '∞', 'φ', 'ε', '∩', '≡', '±',
    '≥', '≤', '⌠', '⌡', '÷', '≈', '°', '∙', '·', '√', 'ⁿ', '²', '■', '\u{00a0}',
];

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cp437_round_trip() {
        let value = "Captain ░ Bible Ç";
        assert_eq!(decode_cp437(&encode_cp437(value).unwrap()), value);
    }
}
