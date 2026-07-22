//! Original-compatible installation policy and launch parsing.

use crate::error::{EngineError, Result};
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct InstallationPolicy {
    pub translation_lock: Option<u8>,
    pub mature_allowed: bool,
    pub no_combat: bool,
}

impl Default for InstallationPolicy {
    fn default() -> Self {
        Self {
            translation_lock: None,
            mature_allowed: true,
            no_combat: false,
        }
    }
}

impl InstallationPolicy {
    pub fn parse(data: &[u8]) -> Result<Self> {
        let [low, high, mature, combat]: [u8; 4] = data.try_into().map_err(|_| {
            EngineError::format(
                "SOUND.5",
                format!("file is {} bytes, expected 4", data.len()),
            )
        })?;
        let lock = u16::from_le_bytes([low, high]);
        let translation_lock = if lock == 0x70 {
            None
        } else if lock <= 3 {
            Some(lock as u8)
        } else {
            return Err(EngineError::format(
                "SOUND.5",
                format!("invalid translation lock {lock:#x}"),
            ));
        };
        Ok(Self {
            translation_lock,
            mature_allowed: mature == 0xdb,
            no_combat: combat != 0,
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ExportRequest {
    pub translation: u8,
    pub filename: PathBuf,
    pub mask: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LaunchConfig {
    pub data_dir: PathBuf,
    pub player_prefix: PathBuf,
    pub translation: u8,
    pub translation_explicit: bool,
    pub filter_mature: bool,
    pub no_combat: bool,
    pub export: Option<ExportRequest>,
}

impl LaunchConfig {
    pub fn parse<I, S>(arguments: I, default_data_dir: impl AsRef<Path>) -> Result<Self>
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let mut data_dir = default_data_dir.as_ref().to_path_buf();
        let mut player = PathBuf::from("DDGAMES");
        let mut translation = 0u8;
        let mut translation_explicit = false;
        let mut filter_mature = false;
        let mut no_combat = false;
        let mut export_translation = None;
        let mut export_filename = None;
        let mut export_mask = 63u8;

        for argument in arguments {
            let argument = argument.as_ref();
            if !argument.starts_with('-') || argument == "-" {
                player = PathBuf::from(argument);
                continue;
            }
            let option = &argument[1..];
            let lower = option.to_ascii_lowercase();
            if lower == "t" {
                filter_mature = true;
            } else if lower == "c" {
                no_combat = true;
            } else if lower.starts_with('b') && option.len() == 2 {
                translation = translation_code(option.as_bytes()[1] as char)?;
                translation_explicit = true;
            } else if lower.starts_with('i') && option.len() > 1 {
                data_dir = PathBuf::from(&option[1..]);
            } else if lower.starts_with('s') && option.len() > 2 {
                export_translation = Some(translation_code(option.as_bytes()[1] as char)?);
                export_filename = Some(PathBuf::from(&option[2..]));
            } else if lower.starts_with('g') && option.len() == 3 {
                export_mask = option[1..].parse::<u8>().map_err(|_| {
                    EngineError::Usage(format!("invalid two-digit export mask: {argument}"))
                })?;
            } else {
                return Err(EngineError::Usage(format!("unknown option: {argument}")));
            }
        }
        let export = match (export_translation, export_filename) {
            (Some(translation), Some(filename)) => Some(ExportRequest {
                translation,
                filename,
                mask: export_mask,
            }),
            _ => None,
        };
        Ok(Self {
            data_dir,
            player_prefix: player,
            translation,
            translation_explicit,
            filter_mature,
            no_combat,
            export,
        })
    }

    pub fn apply_policy(&mut self, policy: InstallationPolicy) {
        if let Some(translation) = policy.translation_lock {
            if !self.translation_explicit {
                self.translation = translation;
            }
            if let Some(export) = &mut self.export {
                export.translation = translation;
            }
        }
        self.filter_mature |= !policy.mature_allowed;
        self.no_combat |= policy.no_combat;
    }
}

pub fn translation_code(code: char) -> Result<u8> {
    match code.to_ascii_uppercase() {
        'K' => Ok(0),
        'N' => Ok(1),
        'R' => Ok(2),
        'L' | 'T' => Ok(3),
        _ => Err(EngineError::Usage(format!(
            "unknown translation code: {code}"
        ))),
    }
}

pub fn translation_letter(index: u8) -> Result<char> {
    match index {
        0 => Ok('K'),
        1 => Ok('N'),
        2 => Ok('R'),
        3 => Ok('T'),
        _ => Err(EngineError::format(
            "settings",
            "translation is out of range",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restrictions_are_monotonic() {
        let mut launch = LaunchConfig::parse(["-bN"], ".").unwrap();
        launch.apply_policy(InstallationPolicy {
            translation_lock: Some(2),
            mature_allowed: false,
            no_combat: true,
        });
        assert_eq!(launch.translation, 1);
        assert!(launch.filter_mature && launch.no_combat);
    }

    #[test]
    fn installation_lock_selects_default_and_export_translation() {
        let mut launch = LaunchConfig::parse(["-sTstudy.txt"], ".").unwrap();
        launch.apply_policy(InstallationPolicy {
            translation_lock: Some(2),
            mature_allowed: true,
            no_combat: false,
        });
        assert_eq!(launch.translation, 2);
        assert_eq!(launch.export.unwrap().translation, 2);
    }
}
