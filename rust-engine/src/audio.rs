//! Original ABT effects and bounded XMIDI validation.

use crate::error::{EngineError, Result, u16_le};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Effect {
    pub sample_rate: u16,
    pub block_samples: u8,
    pub codec: u8,
    pub auxiliary: u16,
    pub samples: Vec<u8>,
}

impl Effect {
    pub fn decode(data: &[u8]) -> Result<Self> {
        if data.len() < 9 {
            return Err(EngineError::format("ABT", "shorter than nine-byte header"));
        }
        let sample_count = u16_le(data, 0, "ABT")? as usize;
        let sample_rate = u16_le(data, 2, "ABT")?;
        let block_samples = data[4];
        let codec = data[5];
        let auxiliary = u16_le(data, 6, "ABT")?;
        if sample_count == 0 || sample_rate == 0 || block_samples == 0 {
            return Err(EngineError::format(
                "ABT",
                "zero sample count, rate, or block size",
            ));
        }
        let mut position = 9usize;
        let mut sample = data[8];
        let mut samples = Vec::with_capacity(sample_count);
        samples.push(sample);
        while samples.len() < sample_count {
            let control = *data
                .get(position)
                .ok_or_else(|| EngineError::format("ABT", "truncated command stream"))?;
            position += 1;
            if control & 0x80 != 0 {
                sample = control << 1;
                samples.push(sample);
            } else if control & 0x40 != 0 {
                let count = usize::from(control & 0x3f);
                if samples.len() + count > sample_count {
                    return Err(EngineError::format("ABT", "run exceeds sample count"));
                }
                samples.extend(std::iter::repeat_n(sample, count));
            } else {
                let mode = control >> 4;
                let bits = if mode == 1 {
                    1
                } else if mode == 2 {
                    2
                } else {
                    4
                };
                let packed_bits = usize::from(block_samples) * bits;
                if packed_bits % 8 != 0 || samples.len() + usize::from(block_samples) > sample_count
                {
                    return Err(EngineError::format("ABT", "invalid delta-block geometry"));
                }
                let encoded_size = packed_bits / 8;
                let encoded = data
                    .get(position..position + encoded_size)
                    .ok_or_else(|| EngineError::format("ABT", "truncated delta block"))?;
                let step = i16::from((control & 0x0f) + 1);
                let table = delta_table(bits, step);
                let mask = (1u8 << bits) - 1;
                for &packed in encoded {
                    for field in (0..8 / bits).rev() {
                        let shift = field * bits;
                        let delta = table[((packed >> shift) & mask) as usize];
                        sample = (i16::from(sample) + delta).clamp(0, 255) as u8;
                        samples.push(sample);
                    }
                }
                position += encoded_size;
            }
        }
        if samples.len() != sample_count || position != data.len() {
            return Err(EngineError::format(
                "ABT",
                "sample count or input consumption mismatch",
            ));
        }
        Ok(Self {
            sample_rate,
            block_samples,
            codec,
            auxiliary,
            samples,
        })
    }
}

fn delta_table(bits: usize, step: i16) -> Vec<i16> {
    let factor = match bits {
        1 => 1,
        2 => 2,
        4 => 8,
        _ => unreachable!(),
    };
    let mut value = (-factor * step) as i8;
    let mut output = Vec::with_capacity(1 << bits);
    for _ in 0..1 << bits {
        output.push(i16::from(value));
        value = value.wrapping_add(step as i8);
        if value == 0 {
            value = step as i8;
        }
    }
    output
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct XmiSummary {
    pub sequences: u16,
    pub event_counts: Vec<usize>,
    pub note_counts: Vec<usize>,
}

/// Validate the exact IFF/XMIDI nesting used by the supplied music.
pub fn validate_xmi(data: &[u8]) -> Result<XmiSummary> {
    let top = chunks(data, 0, data.len())?;
    if top.len() != 2
        || top[0].tag != *b"FORM"
        || top[0].form != Some(*b"XDIR")
        || top[1].tag != *b"CAT "
        || top[1].form != Some(*b"XMID")
    {
        return Err(EngineError::format(
            "XMI",
            "expected FORM XDIR then CAT XMID",
        ));
    }
    let directory_children = chunks(data, top[0].child_start, top[0].end)?;
    if directory_children.len() != 1
        || directory_children[0].tag != *b"INFO"
        || directory_children[0].payload_len != 2
    {
        return Err(EngineError::format("XMI", "invalid XDIR INFO"));
    }
    let info = directory_children[0].payload_start;
    let sequences = u16::from_le_bytes([data[info], data[info + 1]]);
    let forms = chunks(data, top[1].child_start, top[1].end)?;
    if forms.len() != usize::from(sequences) {
        return Err(EngineError::format("XMI", "sequence-count mismatch"));
    }
    let mut event_counts = Vec::new();
    let mut note_counts = Vec::new();
    for form in forms {
        if form.tag != *b"FORM" || form.form != Some(*b"XMID") {
            return Err(EngineError::format("XMI", "catalog child is not FORM XMID"));
        }
        let children = chunks(data, form.child_start, form.end)?;
        if children.len() != 2
            || children[0].tag != *b"TIMB"
            || children[1].tag != *b"EVNT"
            || children[0].payload_len % 2 != 0
        {
            return Err(EngineError::format("XMI", "expected TIMB then EVNT"));
        }
        let event_data = &data[children[1].payload_start..children[1].end];
        let (events, notes) = validate_events(event_data)?;
        event_counts.push(events);
        note_counts.push(notes);
    }
    Ok(XmiSummary {
        sequences,
        event_counts,
        note_counts,
    })
}

#[derive(Clone, Copy)]
struct Chunk {
    tag: [u8; 4],
    form: Option<[u8; 4]>,
    payload_start: usize,
    payload_len: usize,
    child_start: usize,
    end: usize,
}

fn chunks(data: &[u8], start: usize, limit: usize) -> Result<Vec<Chunk>> {
    let mut result = Vec::new();
    let mut position = start;
    while position < limit {
        let header = data
            .get(position..position + 8)
            .ok_or_else(|| EngineError::format("XMI", "truncated IFF header"))?;
        let tag: [u8; 4] = header[..4].try_into().unwrap();
        let size = u32::from_be_bytes(header[4..8].try_into().unwrap()) as usize;
        let payload_start = position + 8;
        let end = payload_start
            .checked_add(size)
            .ok_or_else(|| EngineError::format("XMI", "IFF size overflow"))?;
        if end + (size & 1) > limit {
            return Err(EngineError::format(
                "XMI",
                "IFF chunk exceeds containing region",
            ));
        }
        let container = tag == *b"FORM" || tag == *b"CAT ";
        let form = if container {
            Some(
                data.get(payload_start..payload_start + 4)
                    .ok_or_else(|| EngineError::format("XMI", "container has no type"))?
                    .try_into()
                    .unwrap(),
            )
        } else {
            None
        };
        result.push(Chunk {
            tag,
            form,
            payload_start,
            payload_len: size,
            child_start: payload_start + if container { 4 } else { 0 },
            end,
        });
        position = end + (size & 1);
    }
    if position != limit {
        return Err(EngineError::format("XMI", "IFF chunks are not aligned"));
    }
    Ok(result)
}

fn vlq(data: &[u8], position: &mut usize) -> Result<usize> {
    let mut value = 0usize;
    for _ in 0..4 {
        let byte = *data
            .get(*position)
            .ok_or_else(|| EngineError::format("XMI", "truncated VLQ"))?;
        *position += 1;
        value = (value << 7) | usize::from(byte & 0x7f);
        if byte & 0x80 == 0 {
            return Ok(value);
        }
    }
    Err(EngineError::format("XMI", "VLQ exceeds four bytes"))
}

fn validate_events(data: &[u8]) -> Result<(usize, usize)> {
    let mut position = 0usize;
    let mut events = 0usize;
    let mut notes = 0usize;
    let mut ended = false;
    while position < data.len() {
        if ended {
            if data[position..].iter().any(|&byte| byte != 0) {
                return Err(EngineError::format(
                    "XMI",
                    "nonzero data after end of track",
                ));
            }
            return Ok((events, notes));
        }
        while data.get(position).is_some_and(|byte| *byte < 0x80) {
            position += 1;
        }
        let status = *data
            .get(position)
            .ok_or_else(|| EngineError::format("XMI", "delay has no event"))?;
        position += 1;
        let high = status & 0xf0;
        if (0x80..=0xef).contains(&status) {
            let count = if high == 0xc0 || high == 0xd0 { 1 } else { 2 };
            if position + count > data.len() {
                return Err(EngineError::format("XMI", "truncated channel event"));
            }
            position += count;
            if high == 0x90 {
                vlq(data, &mut position)?;
                notes += 1;
            }
        } else if status == 0xf0 || status == 0xf7 {
            let size = vlq(data, &mut position)?;
            position = position
                .checked_add(size)
                .filter(|&end| end <= data.len())
                .ok_or_else(|| EngineError::format("XMI", "system event exceeds EVNT"))?;
        } else if status == 0xff {
            let kind = *data
                .get(position)
                .ok_or_else(|| EngineError::format("XMI", "truncated meta event"))?;
            position += 1;
            let size = vlq(data, &mut position)?;
            position = position
                .checked_add(size)
                .filter(|&end| end <= data.len())
                .ok_or_else(|| EngineError::format("XMI", "meta event exceeds EVNT"))?;
            if kind == 0x2f {
                if size != 0 {
                    return Err(EngineError::format("XMI", "end of track has payload"));
                }
                ended = true;
            }
        } else {
            return Err(EngineError::format(
                "XMI",
                format!("unsupported status {status:#x}"),
            ));
        }
        events += 1;
    }
    if ended {
        Ok((events, notes))
    } else {
        Err(EngineError::format("XMI", "missing end of track"))
    }
}
