//! Mutable 16x16 world maps and current-cell derivation.

use crate::error::{EngineError, Result};

pub const MAP_WIDTH: usize = 16;
pub const MAP_HEIGHT: usize = 16;
pub const MAP_SIZE: usize = MAP_WIDTH * MAP_HEIGHT * 3;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Cell {
    pub packed: u8,
    pub parameter_a: u8,
    pub parameter_b: u8,
}

impl Cell {
    pub fn connections(self) -> u8 {
        self.packed & 0xf0
    }

    pub fn kind(self) -> u8 {
        self.packed & 0x0f
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WorldMap {
    bytes: [u8; MAP_SIZE],
}

impl Default for WorldMap {
    fn default() -> Self {
        Self {
            bytes: [0; MAP_SIZE],
        }
    }
}

impl WorldMap {
    pub fn parse(data: &[u8]) -> Result<Self> {
        let bytes = data.try_into().map_err(|_| {
            EngineError::format(
                "MAP",
                format!("resource is {} bytes, expected {MAP_SIZE}", data.len()),
            )
        })?;
        Ok(Self { bytes })
    }

    pub fn as_bytes(&self) -> &[u8; MAP_SIZE] {
        &self.bytes
    }

    pub fn cell(&self, x: usize, y: usize) -> Result<Cell> {
        let base = Self::offset(x, y)?;
        Ok(Cell {
            packed: self.bytes[base],
            parameter_a: self.bytes[base + 1],
            parameter_b: self.bytes[base + 2],
        })
    }

    pub fn set_kind_unmasked(&mut self, x: usize, y: usize, value: u8) -> Result<()> {
        let base = Self::offset(x, y)?;
        self.bytes[base] = (self.bytes[base] & 0xf0) | value;
        Ok(())
    }

    pub fn set_parameter_a(&mut self, x: usize, y: usize, value: u8) -> Result<()> {
        let base = Self::offset(x, y)?;
        self.bytes[base + 1] = value;
        Ok(())
    }

    pub fn set_parameter_b(&mut self, x: usize, y: usize, value: u8) -> Result<()> {
        let base = Self::offset(x, y)?;
        self.bytes[base + 2] = value;
        Ok(())
    }

    /// Apply the original full-grid normalizer used by opcode 0x87.
    pub fn normalize(&mut self) {
        for cell in self.bytes.chunks_exact_mut(3) {
            if cell[0] & 0xf0 == 0 {
                cell[2] = 0;
                continue;
            }
            match cell[0] & 0x0f {
                6 => {
                    cell[0] = (cell[0] & 0xf0) | 0x0a;
                    cell[1] = cell[2];
                    cell[2] = 0;
                }
                1..=9 => cell[0] = (cell[0] & 0xf0) | 0x0b,
                _ => {}
            }
        }
    }

    fn offset(x: usize, y: usize) -> Result<usize> {
        if x >= MAP_WIDTH || y >= MAP_HEIGHT {
            return Err(EngineError::format(
                "MAP",
                format!("coordinate ({x},{y}) is out of range"),
            ));
        }
        Ok(3 * (MAP_WIDTH * y + x))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CellContext {
    pub kind_or_room_class: i16,
    /// A new value for VM variable 14. The original leaves the variable
    /// unchanged when a connected cell has no usable forward row.
    pub entrance_or_neighbor: Option<i16>,
    /// A new value for VM variable 15, populated from two rows forward.
    pub second_forward_kind: Option<i16>,
    pub parameter_a: i16,
    pub parameter_b: i16,
    pub adjacent_room_b: [i16; 3],
    pub flags: [bool; 0x30],
}

impl Default for CellContext {
    fn default() -> Self {
        Self {
            kind_or_room_class: 0,
            entrance_or_neighbor: None,
            second_forward_kind: None,
            parameter_a: 0,
            parameter_b: 0,
            adjacent_room_b: [0; 3],
            flags: [false; 0x30],
        }
    }
}

impl WorldMap {
    /// Reproduce `process_current_map_cell`, including all transient flags.
    ///
    /// The forward scan is screen-oriented: it follows decreasing map Y and
    /// only runs when the current cell has an upward connection. Room sides
    /// are checked through the executable's table at load offset 0xED7A.
    pub fn context(&self, x: usize, y: usize) -> Result<CellContext> {
        let cell = self.cell(x, y)?;
        let mut result = CellContext {
            kind_or_room_class: i16::from(cell.kind()),
            parameter_a: i16::from(cell.parameter_a),
            parameter_b: i16::from(cell.parameter_b),
            ..CellContext::default()
        };
        if cell.connections() == 0 {
            result.flags[0x10] = true;
            let adjusted = i16::from(cell.kind()) - 1;
            result.kind_or_room_class = adjusted / 3;
            result.entrance_or_neighbor = Some(adjusted % 3);
            return Ok(result);
        }

        // Movement/action directions on the current hall cell.
        result.flags[0x00] = cell.connections() & 0x20 != 0; // down
        result.flags[0x03] = cell.connections() & 0x40 != 0; // left
        result.flags[0x01] = cell.connections() & 0x80 != 0; // right

        // Side rooms immediately adjacent to the current hall.
        for (nx, orientation, flag, trap_flag, value_index, value_flag) in [
            (x.checked_add(1), 2, 0x02, 0x1f, 0, 0x16),
            (x.checked_sub(1), 1, 0x04, 0x20, 1, 0x17),
        ] {
            let Some(nx) = nx.filter(|&nx| nx < MAP_WIDTH) else {
                continue;
            };
            let room = self.cell(nx, y)?;
            if room_orientation(room) == orientation {
                result.flags[flag] = true;
                result.flags[trap_flag] = room_class(room) == Some(1);
                result.adjacent_room_b[value_index] = i16::from(room.parameter_b);
                result.flags[value_flag] = room.parameter_b != 0;
            }
        }

        if y > 0 {
            let room = self.cell(x, y - 1)?;
            if room_orientation(room) == 3 {
                result.flags[0x11] = true;
                result.flags[0x21] = room_class(room) == Some(1);
                result.adjacent_room_b[2] = i16::from(room.parameter_b);
                result.flags[0x18] = room.parameter_b != 0;
            }
        }

        result.flags[0x05] = cell.connections() & 0x10 != 0; // up
        if !result.flags[0x05] || y == 0 {
            return Ok(result);
        }

        // One row forward. Variable 14 is the direct cell's low kind.
        let forward = self.cell(x, y - 1)?;
        result.entrance_or_neighbor = Some(i16::from(forward.kind()));
        result.flags[0x08] = forward.connections() & 0x40 != 0;
        result.flags[0x06] = forward.connections() & 0x80 != 0;
        result.flags[0x0a] = forward.connections() & 0x10 != 0;
        self.mark_forward_side_room(&mut result, x.checked_add(1), y - 1, 2, 0x07, 0x19)?;
        self.mark_forward_side_room(&mut result, x.checked_sub(1), y - 1, 1, 0x09, 0x1a)?;

        if y <= 1 {
            return Ok(result);
        }

        // Two rows forward. A direct north-facing room is actionable, then
        // the same byte is also interpreted as the second perspective row.
        let second = self.cell(x, y - 2)?;
        if room_orientation(second) == 3 {
            result.flags[0x12] = true;
            result.flags[0x1b] = second.parameter_b != 0;
        }
        result.second_forward_kind = Some(i16::from(second.kind()));
        result.flags[0x0d] = second.connections() & 0x40 != 0;
        result.flags[0x0b] = second.connections() & 0x80 != 0;
        result.flags[0x0f] = second.connections() & 0x10 != 0;
        self.mark_forward_side_room(&mut result, x.checked_add(1), y - 2, 2, 0x0c, 0x1c)?;
        self.mark_forward_side_room(&mut result, x.checked_sub(1), y - 2, 1, 0x0e, 0x1d)?;

        if y > 2 {
            let third = self.cell(x, y - 3)?;
            if room_orientation(third) == 3 {
                result.flags[0x13] = true;
                result.flags[0x1e] = third.parameter_b != 0;
            }
        }
        Ok(result)
    }

    fn mark_forward_side_room(
        &self,
        result: &mut CellContext,
        x: Option<usize>,
        y: usize,
        orientation: u8,
        presence_flag: usize,
        value_flag: usize,
    ) -> Result<()> {
        let Some(x) = x.filter(|&x| x < MAP_WIDTH) else {
            return Ok(());
        };
        let room = self.cell(x, y)?;
        if room_orientation(room) == orientation {
            result.flags[presence_flag] = true;
            result.flags[value_flag] = room.parameter_b != 0;
        }
        Ok(())
    }
}

/// `room_entrance_code_by_kind` from load offset 0xED7A.
const ROOM_ORIENTATION: [u8; 16] = [0, 2, 1, 3, 2, 1, 3, 2, 1, 3, 2, 1, 3, 2, 1, 3];

fn room_orientation(cell: Cell) -> u8 {
    if cell.packed < 0x10 {
        ROOM_ORIENTATION[usize::from(cell.packed)]
    } else {
        0
    }
}

fn room_class(cell: Cell) -> Option<u8> {
    (cell.packed > 0 && cell.packed < 0x10).then(|| (cell.packed - 1) / 3)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn room_context_uses_quotient_and_remainder() {
        let mut map = WorldMap::default();
        map.bytes[0..3].copy_from_slice(&[0x0b, 12, 34]);
        let context = map.context(0, 0).unwrap();
        assert_eq!(context.kind_or_room_class, 3);
        assert_eq!(context.entrance_or_neighbor, Some(1));
        assert_eq!((context.parameter_a, context.parameter_b), (12, 34));
        assert!(context.flags[0x10]);
    }

    #[test]
    fn hall_context_matches_forward_room_scan() {
        let mut map = WorldMap::default();
        let mut put = |x: usize, y: usize, packed: u8, b: u8| {
            let base = WorldMap::offset(x, y).unwrap();
            map.bytes[base..base + 3].copy_from_slice(&[packed, 0, b]);
        };
        put(5, 5, 0xf0, 0); // all four current-hall directions
        put(6, 5, 4, 11); // right Trap
        put(4, 5, 5, 12); // left Trap
        put(5, 4, 6, 13); // above Trap and first forward kind
        put(6, 4, 1, 14);
        put(4, 4, 2, 15);
        put(5, 3, 3, 16);
        put(6, 3, 4, 17);
        put(4, 3, 5, 18);
        put(5, 2, 6, 19);

        let context = map.context(5, 5).unwrap();
        assert_eq!(context.entrance_or_neighbor, Some(6));
        assert_eq!(context.second_forward_kind, Some(3));
        assert_eq!(context.adjacent_room_b, [11, 12, 13]);
        for flag in 0x00..=0x05 {
            assert!(context.flags[flag], "current flag {flag:#x}");
        }
        for flag in [0x07, 0x09] {
            assert!(context.flags[flag], "first row flag {flag:#x}");
        }
        for flag in [0x0c, 0x0e, 0x12, 0x13] {
            assert!(context.flags[flag], "far room flag {flag:#x}");
        }
        for flag in 0x16..=0x21 {
            assert!(context.flags[flag], "room state flag {flag:#x}");
        }
    }

    #[test]
    fn forward_hall_connections_set_perspective_flags() {
        let mut map = WorldMap::default();
        map.bytes[WorldMap::offset(1, 3).unwrap()] = 0x10;
        map.bytes[WorldMap::offset(1, 2).unwrap()] = 0xd7;
        map.bytes[WorldMap::offset(1, 1).unwrap()] = 0xd9;
        let context = map.context(1, 3).unwrap();
        assert_eq!(context.entrance_or_neighbor, Some(7));
        assert_eq!(context.second_forward_kind, Some(9));
        for flag in [0x05, 0x08, 0x0a, 0x0d, 0x0f] {
            assert!(context.flags[flag], "perspective flag {flag:#x}");
        }
        for flag in [0x06, 0x0b] {
            assert!(context.flags[flag], "rightward perspective flag {flag:#x}");
        }
    }

    #[test]
    fn kind_write_is_intentionally_unmasked() {
        let mut map = WorldMap::default();
        map.bytes[0] = 0xa2;
        map.set_kind_unmasked(0, 0, 0x35).unwrap();
        assert_eq!(map.bytes[0], 0xb5);
    }

    #[test]
    fn normalization_matches_room_station_and_encounter_rules() {
        let mut map = WorldMap::default();
        map.bytes[0..12].copy_from_slice(&[
            0x04, 1, 2, // zero-mask room: clear B only
            0x26, 3, 4, // guarded station: expose B as A
            0x89, 5, 6, // encounter: replace kind with B
            0x2c, 7, 8, // other hall kind: unchanged
        ]);
        map.normalize();
        assert_eq!(
            &map.bytes[0..12],
            &[0x04, 1, 0, 0x2a, 4, 0, 0x8b, 5, 6, 0x2c, 7, 8]
        );
    }
}
