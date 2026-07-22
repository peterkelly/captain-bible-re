//! Original 243-byte label indexes and 2,752-byte state images.

use crate::error::{EngineError, Result};
use crate::state::{Checkpoint, GameState, VARIABLE_COUNT};
use crate::text::{DESCRIPTOR_COUNT, TextBank, decode_cp437, encode_cp437};
use crate::world::{MAP_SIZE, WorldMap};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

pub const INDEX_SIZE: usize = 243;
pub const STATE_SIZE: usize = 2752;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SaveIndex {
    pub labels: [String; 9],
}

impl Default for SaveIndex {
    fn default() -> Self {
        Self {
            labels: std::array::from_fn(|_| "(EMPTY)".to_owned()),
        }
    }
}

impl SaveIndex {
    pub fn parse(data: &[u8]) -> Result<Self> {
        if data.len() != INDEX_SIZE {
            return Err(EngineError::format(
                "SV0",
                format!("file is {} bytes, expected {INDEX_SIZE}", data.len()),
            ));
        }
        let mut labels: [String; 9] = std::array::from_fn(|_| String::new());
        for (slot, label) in labels.iter_mut().enumerate() {
            *label = c_string(&data[slot * 27..slot * 27 + 27], "save label")?;
        }
        Ok(Self { labels })
    }

    pub fn encode(&self) -> Result<[u8; INDEX_SIZE]> {
        let mut output = [0; INDEX_SIZE];
        for (slot, label) in self.labels.iter().enumerate() {
            let encoded = encode_cp437(label)?;
            if encoded.len() > 26 {
                return Err(EngineError::format("SV0", "label exceeds 26 bytes"));
            }
            output[slot * 27..slot * 27 + encoded.len()].copy_from_slice(&encoded);
        }
        Ok(output)
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SavedDescriptor {
    pub state: u8,
    pub selector: u8,
    pub offset: u16,
    pub span: u16,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SaveImage {
    pub checkpoint: Checkpoint,
    pub live_variables: [i16; VARIABLE_COUNT],
    pub live_descriptors: [SavedDescriptor; DESCRIPTOR_COUNT],
    pub live_scene_name: String,
    pub live_scene_entry: String,
    pub translation: u16,
    pub music_enabled: u16,
    pub effects_enabled: u16,
    pub live_text_bank: u8,
    pub live_world: WorldMap,
}

impl SaveImage {
    pub fn parse(data: &[u8]) -> Result<Self> {
        if data.len() != STATE_SIZE {
            return Err(EngineError::format(
                "save state",
                format!("file is {} bytes, expected {STATE_SIZE}", data.len()),
            ));
        }
        let checkpoint_variables = decode_variables(&data[0..0xc8]);
        let live_variables = decode_variables(&data[0xc8..0x190]);
        let checkpoint_states: [u8; DESCRIPTOR_COUNT] = data[0x190..0x1d2].try_into().unwrap();
        let mut live_descriptors = [SavedDescriptor::default(); DESCRIPTOR_COUNT];
        for (index, descriptor) in live_descriptors.iter_mut().enumerate() {
            let base = 0x1d2 + index * 10;
            *descriptor = SavedDescriptor {
                state: data[base + 4],
                selector: data[base + 5],
                offset: word(data, base + 6),
                span: word(data, base + 8),
            };
        }
        let checkpoint_scene_name = c_string(&data[0x466..0x47a], "checkpoint scene")?;
        let live_scene_name = c_string(&data[0x47a..0x48e], "live scene")?;
        let checkpoint_scene_entry = c_string(&data[0x48e..0x4a2], "checkpoint scene entry")?;
        let live_scene_entry = c_string(&data[0x4a2..0x4b6], "live scene entry")?;
        let translation = word(data, 0x4b6);
        if translation > 3 {
            return Err(EngineError::format(
                "save state",
                "translation is out of range",
            ));
        }
        let checkpoint_text_bank = bank(word(data, 0x4bc))?;
        let live_text_bank = bank(word(data, 0x4be))?;
        for descriptor in &live_descriptors {
            let end = usize::from(descriptor.offset) + usize::from(descriptor.span);
            if end > u16::MAX as usize {
                return Err(EngineError::format(
                    "save state",
                    "descriptor span overflows",
                ));
            }
        }
        let live_world = WorldMap::parse(&data[0x4c0..0x4c0 + MAP_SIZE])?;
        let checkpoint_world = WorldMap::parse(&data[0x7c0..0x7c0 + MAP_SIZE])?;
        Ok(Self {
            checkpoint: Checkpoint {
                variables: checkpoint_variables,
                text_states: checkpoint_states,
                scene_name: checkpoint_scene_name,
                scene_entry: checkpoint_scene_entry,
                text_bank: checkpoint_text_bank,
                world: checkpoint_world,
            },
            live_variables,
            live_descriptors,
            live_scene_name,
            live_scene_entry,
            translation,
            music_enabled: word(data, 0x4b8),
            effects_enabled: word(data, 0x4ba),
            live_text_bank,
            live_world,
        })
    }

    pub fn from_state(state: &GameState) -> Self {
        let mut live_descriptors = [SavedDescriptor::default(); DESCRIPTOR_COUNT];
        if let Some(text) = &state.text {
            for (saved, descriptor) in live_descriptors.iter_mut().zip(&text.descriptors) {
                *saved = SavedDescriptor {
                    state: descriptor.state,
                    selector: descriptor.selector,
                    offset: descriptor.companion_offset,
                    span: descriptor.companion_span,
                };
            }
        }
        Self {
            checkpoint: state.checkpoint.clone(),
            live_variables: state.variables,
            live_descriptors,
            live_scene_name: state.scene_name.clone(),
            live_scene_entry: state.scene_entry.clone(),
            translation: state.translation,
            music_enabled: state.music_enabled,
            effects_enabled: state.effects_enabled,
            live_text_bank: state.text_bank,
            live_world: state.world.clone(),
        }
    }

    pub fn encode(&self) -> Result<[u8; STATE_SIZE]> {
        let mut output = [0; STATE_SIZE];
        encode_variables(&mut output[0..0xc8], &self.checkpoint.variables);
        encode_variables(&mut output[0xc8..0x190], &self.live_variables);
        output[0x190..0x1d2].copy_from_slice(&self.checkpoint.text_states);
        for (index, descriptor) in self.live_descriptors.iter().enumerate() {
            let base = 0x1d2 + index * 10;
            output[base + 4] = descriptor.state;
            output[base + 5] = descriptor.selector;
            put_word(&mut output, base + 6, descriptor.offset);
            put_word(&mut output, base + 8, descriptor.span);
        }
        put_c_string(&mut output[0x466..0x47a], &self.checkpoint.scene_name)?;
        put_c_string(&mut output[0x47a..0x48e], &self.live_scene_name)?;
        put_c_string(&mut output[0x48e..0x4a2], &self.checkpoint.scene_entry)?;
        put_c_string(&mut output[0x4a2..0x4b6], &self.live_scene_entry)?;
        put_word(&mut output, 0x4b6, self.translation);
        put_word(&mut output, 0x4b8, self.music_enabled);
        put_word(&mut output, 0x4ba, self.effects_enabled);
        put_word(&mut output, 0x4bc, u16::from(self.checkpoint.text_bank));
        put_word(&mut output, 0x4be, u16::from(self.live_text_bank));
        output[0x4c0..0x7c0].copy_from_slice(self.live_world.as_bytes());
        output[0x7c0..0xac0].copy_from_slice(self.checkpoint.world.as_bytes());
        Ok(output)
    }

    pub fn into_state(self, text: Option<TextBank>) -> GameState {
        GameState {
            variables: self.live_variables,
            translation: self.translation,
            music_enabled: self.music_enabled,
            effects_enabled: self.effects_enabled,
            text,
            text_bank: self.live_text_bank,
            world: self.live_world,
            auxiliary_cells: [0; 256],
            scene_name: self.live_scene_name,
            scene_entry: self.live_scene_entry,
            checkpoint: self.checkpoint,
        }
    }
}

pub fn atomic_write(path: &Path, data: &[u8]) -> Result<()> {
    let mut temporary = PathBuf::from(path);
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("save");
    temporary.set_extension(format!("{extension}.{}.tmp", std::process::id()));
    let result = (|| -> Result<()> {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)?;
        file.write_all(data)?;
        file.sync_all()?;
        drop(file);
        fs::rename(&temporary, path)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

fn word(data: &[u8], offset: usize) -> u16 {
    u16::from_le_bytes([data[offset], data[offset + 1]])
}
fn put_word(data: &mut [u8], offset: usize, value: u16) {
    data[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}
fn decode_variables(data: &[u8]) -> [i16; VARIABLE_COUNT] {
    std::array::from_fn(|index| i16::from_le_bytes([data[index * 2], data[index * 2 + 1]]))
}
fn encode_variables(data: &mut [u8], values: &[i16; VARIABLE_COUNT]) {
    for (chunk, value) in data.chunks_exact_mut(2).zip(values) {
        chunk.copy_from_slice(&value.to_le_bytes());
    }
}
fn bank(value: u16) -> Result<u8> {
    if value == 0
        || (u16::from(b'A')..=u16::from(b'G')).contains(&value)
        || value == u16::from(b'R')
    {
        Ok(value as u8)
    } else {
        Err(EngineError::format(
            "save state",
            format!("invalid text bank {value:#x}"),
        ))
    }
}
fn c_string(data: &[u8], context: &str) -> Result<String> {
    let end = data
        .iter()
        .position(|&byte| byte == 0)
        .ok_or_else(|| EngineError::format(context, "unterminated fixed string"))?;
    Ok(decode_cp437(&data[..end]))
}
fn put_c_string(data: &mut [u8], value: &str) -> Result<()> {
    let encoded = encode_cp437(value)?;
    if encoded.len() >= data.len() {
        return Err(EngineError::format(
            "save state",
            "fixed string is too long",
        ));
    }
    data.fill(0);
    data[..encoded.len()].copy_from_slice(&encoded);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn state_round_trip() {
        let mut state = GameState::default();
        state.variables[21] = 10_000;
        state.scene_name = "FIRST".into();
        state.snapshot();
        let bytes = SaveImage::from_state(&state).encode().unwrap();
        let parsed = SaveImage::parse(&bytes).unwrap();
        assert_eq!(parsed.live_variables[21], 10_000);
        assert_eq!(parsed.live_scene_name, "FIRST");
    }
}
