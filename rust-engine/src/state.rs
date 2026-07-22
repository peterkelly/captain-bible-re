//! Persistent script state and checkpoint semantics.

use crate::text::{DESCRIPTOR_COUNT, TextBank};
use crate::world::WorldMap;

pub const VARIABLE_COUNT: usize = 100;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Checkpoint {
    pub variables: [i16; VARIABLE_COUNT],
    pub text_states: [u8; DESCRIPTOR_COUNT],
    pub scene_name: String,
    pub scene_entry: String,
    pub text_bank: u8,
    pub world: WorldMap,
}

impl Default for Checkpoint {
    fn default() -> Self {
        Self {
            variables: [0; VARIABLE_COUNT],
            text_states: [0; DESCRIPTOR_COUNT],
            scene_name: "LOGO".to_owned(),
            scene_entry: String::new(),
            text_bank: 0,
            world: WorldMap::default(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GameState {
    pub variables: [i16; VARIABLE_COUNT],
    pub translation: u16,
    pub music_enabled: u16,
    pub effects_enabled: u16,
    pub text: Option<TextBank>,
    pub text_bank: u8,
    pub world: WorldMap,
    pub auxiliary_cells: [u8; 256],
    pub scene_name: String,
    pub scene_entry: String,
    pub checkpoint: Checkpoint,
}

impl Default for GameState {
    fn default() -> Self {
        Self {
            variables: [0; VARIABLE_COUNT],
            translation: 0,
            music_enabled: 1,
            effects_enabled: 1,
            text: None,
            text_bank: 0,
            world: WorldMap::default(),
            auxiliary_cells: [0; 256],
            scene_name: "LOGO".to_owned(),
            scene_entry: String::new(),
            checkpoint: Checkpoint::default(),
        }
    }
}

impl GameState {
    pub fn variable_index(encoded_offset: u16) -> std::result::Result<usize, String> {
        if encoded_offset & 1 != 0 || encoded_offset >= (VARIABLE_COUNT * 2) as u16 {
            Err(format!("invalid variable byte offset {encoded_offset:#x}"))
        } else {
            Ok(usize::from(encoded_offset / 2))
        }
    }

    pub fn variable(&self, encoded_offset: u16) -> std::result::Result<i16, String> {
        Ok(self.variables[Self::variable_index(encoded_offset)?])
    }

    pub fn set_variable(
        &mut self,
        encoded_offset: u16,
        value: i16,
    ) -> std::result::Result<(), String> {
        let index = Self::variable_index(encoded_offset)?;
        self.variables[index] = value;
        Ok(())
    }

    pub fn flag(&self, identifier: u8) -> bool {
        let word = 3 + usize::from(identifier >> 4);
        self.variables[word] as u16 & (1 << (identifier & 15)) != 0
    }

    pub fn set_flag(&mut self, identifier: u8, enabled: bool) {
        let word = 3 + usize::from(identifier >> 4);
        let mask = 1u16 << (identifier & 15);
        let value = self.variables[word] as u16;
        self.variables[word] = if enabled { value | mask } else { value & !mask } as i16;
    }

    pub fn snapshot(&mut self) {
        let mut text_states = [0; DESCRIPTOR_COUNT];
        if let Some(text) = &self.text {
            for (destination, descriptor) in text_states.iter_mut().zip(&text.descriptors) {
                *destination = descriptor.state;
            }
        }
        self.checkpoint = Checkpoint {
            variables: self.variables,
            text_states,
            scene_name: self.scene_name.clone(),
            scene_entry: self.scene_entry.clone(),
            text_bank: self.text_bank,
            world: self.world.clone(),
        };
    }

    /// Apply the retained checkpoint after a save image has been decoded and
    /// its text bank has been reconstructed by the engine.
    pub fn restore_checkpoint(&mut self) {
        self.variables = self.checkpoint.variables;
        self.scene_name.clone_from(&self.checkpoint.scene_name);
        self.scene_entry.clone_from(&self.checkpoint.scene_entry);
        self.text_bank = self.checkpoint.text_bank;
        self.world.clone_from(&self.checkpoint.world);
        if let Some(text) = &mut self.text {
            for (descriptor, &state) in text
                .descriptors
                .iter_mut()
                .zip(&self.checkpoint.text_states)
            {
                descriptor.state = state;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn flags_alias_variable_words() {
        let mut state = GameState::default();
        state.set_flag(0x30, true);
        assert!(state.flag(0x30));
        assert_eq!(state.variables[6], 1);
    }
    #[test]
    fn rejects_odd_variable_offsets() {
        assert!(GameState::variable_index(3).is_err());
    }
}
