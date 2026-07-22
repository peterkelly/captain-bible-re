use std::fmt::{self, Display, Formatter};
use std::io;

/// The engine's bounded error type.  Malformed input is reported instead of
/// being allowed to partially mutate live game state.
#[derive(Debug)]
pub enum EngineError {
    Format {
        context: String,
        message: String,
    },
    MissingResource(String),
    Vm {
        scene: String,
        offset: usize,
        message: String,
    },
    Io(io::Error),
    Usage(String),
}

impl EngineError {
    pub fn format(context: impl Into<String>, message: impl Into<String>) -> Self {
        Self::Format {
            context: context.into(),
            message: message.into(),
        }
    }

    pub fn vm(scene: impl Into<String>, offset: usize, message: impl Into<String>) -> Self {
        Self::Vm {
            scene: scene.into(),
            offset,
            message: message.into(),
        }
    }
}

impl Display for EngineError {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::Format { context, message } => write!(f, "{context}: {message}"),
            Self::MissingResource(name) => write!(f, "resource not found: {name}"),
            Self::Vm {
                scene,
                offset,
                message,
            } => {
                write!(f, "{scene}.BIN at {offset:#06x}: {message}")
            }
            Self::Io(error) => Display::fmt(error, f),
            Self::Usage(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for EngineError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(error) => Some(error),
            _ => None,
        }
    }
}

impl From<io::Error> for EngineError {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}

pub type Result<T> = std::result::Result<T, EngineError>;

pub(crate) fn u16_le(data: &[u8], offset: usize, context: &str) -> Result<u16> {
    let bytes = data
        .get(offset..offset + 2)
        .ok_or_else(|| EngineError::format(context, format!("truncated word at {offset:#x}")))?;
    Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
}

pub(crate) fn i16_le(data: &[u8], offset: usize, context: &str) -> Result<i16> {
    Ok(u16_le(data, offset, context)? as i16)
}

pub(crate) fn u32_le(data: &[u8], offset: usize, context: &str) -> Result<u32> {
    let bytes = data
        .get(offset..offset + 4)
        .ok_or_else(|| EngineError::format(context, format!("truncated dword at {offset:#x}")))?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}
