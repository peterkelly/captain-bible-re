//! Indexed artwork, palettes, and the logical 320x200 framebuffer.

use crate::error::{EngineError, Result, i16_le, u16_le, u32_le};

pub const SCREEN_WIDTH: usize = 320;
pub const SCREEN_HEIGHT: usize = 200;
pub const SCREEN_PIXELS: usize = SCREEN_WIDTH * SCREEN_HEIGHT;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Palette {
    /// Six-bit VGA RGB components.
    pub components: [u8; 768],
}

impl Default for Palette {
    fn default() -> Self {
        Self {
            components: [0; 768],
        }
    }
}

impl Palette {
    pub fn parse(data: &[u8]) -> Result<Self> {
        let components: [u8; 768] = data.try_into().map_err(|_| {
            EngineError::format(
                "PAL",
                format!("resource is {} bytes, expected 768", data.len()),
            )
        })?;
        if let Some(value) = components.iter().find(|&&value| value > 63) {
            return Err(EngineError::format(
                "PAL",
                format!("component exceeds six bits: {value:#x}"),
            ));
        }
        Ok(Self { components })
    }

    pub fn rgb(&self, index: u8) -> [u8; 3] {
        let base = index as usize * 3;
        let expand = |value: u8| (value << 2) | (value >> 4);
        [
            expand(self.components[base]),
            expand(self.components[base + 1]),
            expand(self.components[base + 2]),
        ]
    }

    pub fn rgba8888(&self) -> [u32; 256] {
        std::array::from_fn(|index| {
            let [red, green, blue] = self.rgb(index as u8);
            0xff00_0000 | ((red as u32) << 16) | ((green as u32) << 8) | blue as u32
        })
    }

    pub fn black(&mut self) {
        self.components.fill(0);
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ArtFrame {
    pub origin_x: i16,
    pub origin_y: i16,
    pub width: u16,
    pub height: u16,
    pub pixels: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Art {
    pub frames: Vec<ArtFrame>,
}

impl Art {
    pub fn parse(data: &[u8]) -> Result<Self> {
        if data.len() < 12 {
            return Err(EngineError::format("ART", "shorter than one descriptor"));
        }
        let first_offset = u32_le(data, 8, "ART")? as usize;
        if first_offset < 12 || !first_offset.is_multiple_of(12) || first_offset > data.len() {
            return Err(EngineError::format("ART", "invalid descriptor-table size"));
        }
        let count = first_offset / 12;
        let mut expected = first_offset;
        let mut frames = Vec::with_capacity(count);
        for index in 0..count {
            let base = index * 12;
            let origin_x = i16_le(data, base, "ART")?;
            let origin_y = i16_le(data, base + 2, "ART")?;
            let width = u16_le(data, base + 4, "ART")?;
            let height = u16_le(data, base + 6, "ART")?;
            let offset = u32_le(data, base + 8, "ART")? as usize;
            if width == 0 || height == 0 {
                return Err(EngineError::format(
                    "ART",
                    format!("frame {index} is empty"),
                ));
            }
            if offset != expected {
                return Err(EngineError::format(
                    "ART",
                    format!("frame {index} begins at {offset:#x}, expected {expected:#x}"),
                ));
            }
            let size = usize::from(width)
                .checked_mul(usize::from(height))
                .ok_or_else(|| EngineError::format("ART", "pixel-count overflow"))?;
            let end = offset
                .checked_add(size)
                .ok_or_else(|| EngineError::format("ART", "frame-end overflow"))?;
            let pixels = data
                .get(offset..end)
                .ok_or_else(|| EngineError::format("ART", format!("frame {index} exceeds EOF")))?
                .to_vec();
            frames.push(ArtFrame {
                origin_x,
                origin_y,
                width,
                height,
                pixels,
            });
            expected = end;
        }
        if expected != data.len() {
            return Err(EngineError::format(
                "ART",
                format!("{} trailing bytes", data.len() - expected),
            ));
        }
        Ok(Self { frames })
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Framebuffer {
    pixels: Vec<u8>,
}

impl Default for Framebuffer {
    fn default() -> Self {
        Self {
            pixels: vec![0; SCREEN_PIXELS],
        }
    }
}

impl Framebuffer {
    pub fn pixels(&self) -> &[u8] {
        &self.pixels
    }

    pub fn fill(&mut self, color: u8) {
        self.pixels.fill(color);
    }

    pub fn draw(
        &mut self,
        frame: &ArtFrame,
        x: i16,
        y: i16,
        scale: u16,
        flags: u8,
        transparent_zero: bool,
    ) {
        if scale == 0 {
            return;
        }
        let source_width = i32::from(frame.width);
        let source_height = i32::from(frame.height);
        let scale = i32::from(scale);
        // The on-disk value is an inverse 8.8 scale divisor.  The DOS
        // renderer divides both dimensions and signed origins by it.
        let width = (source_width << 8) / scale;
        let height = (source_height << 8) / scale;
        if width <= 0 || height <= 0 {
            return;
        }
        let origin_x = (i32::from(frame.origin_x) << 8) / scale;
        let origin_y = (i32::from(frame.origin_y) << 8) / scale;
        let flip_x = flags & 1 != 0;
        let flip_y = flags & 2 != 0;
        let left = if flip_x {
            i32::from(x) - origin_x - width
        } else {
            i32::from(x) + origin_x
        };
        let top = if flip_y {
            i32::from(y) - origin_y - height
        } else {
            i32::from(y) + origin_y
        };

        for destination_y in 0..height {
            let screen_y = top + destination_y;
            if !(0..SCREEN_HEIGHT as i32).contains(&screen_y) {
                continue;
            }
            let mut source_y = (destination_y * scale / 256).min(source_height - 1);
            if flip_y {
                source_y = source_height - 1 - source_y;
            }
            for destination_x in 0..width {
                let screen_x = left + destination_x;
                if !(0..SCREEN_WIDTH as i32).contains(&screen_x) {
                    continue;
                }
                let mut source_x = (destination_x * scale / 256).min(source_width - 1);
                if flip_x {
                    source_x = source_width - 1 - source_x;
                }
                let value = frame.pixels[(source_y * source_width + source_x) as usize];
                if !transparent_zero || value != 0 {
                    self.pixels[screen_y as usize * SCREEN_WIDTH + screen_x as usize] = value;
                }
            }
        }
    }

    pub fn rgb_bytes(&self, palette: &Palette) -> Vec<u8> {
        let mut output = Vec::with_capacity(SCREEN_PIXELS * 3);
        for &index in &self.pixels {
            output.extend_from_slice(&palette.rgb(index));
        }
        output
    }

    /// Write a dependency-free PPM screenshot for headless runs and tests.
    pub fn ppm(&self, palette: &Palette) -> Vec<u8> {
        let mut output = format!("P6\n{} {}\n255\n", SCREEN_WIDTH, SCREEN_HEIGHT).into_bytes();
        output.extend_from_slice(&self.rgb_bytes(palette));
        output
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drawing_clips_and_honors_transparency() {
        let frame = ArtFrame {
            origin_x: -1,
            origin_y: 0,
            width: 2,
            height: 1,
            pixels: vec![3, 0],
        };
        let mut target = Framebuffer::default();
        target.fill(7);
        target.draw(&frame, 1, 0, 0x100, 0, true);
        assert_eq!(&target.pixels()[0..2], &[3, 7]);
    }

    #[test]
    fn reflected_drawing_reflects_the_frame_origin_about_the_anchor() {
        let frame = ArtFrame {
            origin_x: 207,
            origin_y: 0,
            width: 101,
            height: 1,
            pixels: vec![3; 101],
        };
        let mut target = Framebuffer::default();
        target.draw(&frame, 303, 0, 0x100, 1, true);
        assert!(target.pixels()[0..96].iter().all(|&pixel| pixel == 3));
        assert_eq!(target.pixels()[96], 0);
    }

    #[test]
    fn scale_is_an_inverse_fixed_point_divisor() {
        let frame = ArtFrame {
            origin_x: -2,
            origin_y: 0,
            width: 4,
            height: 2,
            pixels: vec![1, 2, 3, 4, 5, 6, 7, 8],
        };
        let mut target = Framebuffer::default();
        target.draw(&frame, 10, 0, 0x200, 0, true);
        assert_eq!(&target.pixels()[8..12], &[0, 1, 3, 0]);
    }

    #[test]
    fn palette_expands_vga_components() {
        let mut raw = [0; 768];
        raw[3..6].copy_from_slice(&[63, 32, 1]);
        let palette = Palette::parse(&raw).unwrap();
        assert_eq!(palette.rgb(1), [255, 130, 4]);
    }
}
