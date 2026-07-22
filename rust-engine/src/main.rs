use captain_bible_engine::archive::Archive;
use captain_bible_engine::audio::{Effect, validate_xmi};
use captain_bible_engine::bytecode::{code_regions, decode};
use captain_bible_engine::config::{InstallationPolicy, LaunchConfig};
use captain_bible_engine::graphics::{Art, Palette};
use captain_bible_engine::save::{SaveImage, SaveIndex};
use captain_bible_engine::text::{TextBank, export_study};
use captain_bible_engine::world::WorldMap;
use captain_bible_engine::{Engine, EngineError, EngineEvent, EngineStatus, InputEvent, Result};
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[derive(Debug, PartialEq, Eq)]
struct CommandLine {
    data_dir: PathBuf,
    validate: bool,
    ticks: Option<usize>,
    auto_confirm: bool,
    headless: bool,
    screenshot: Option<PathBuf>,
    original_options: Vec<String>,
    help: bool,
}

impl Default for CommandLine {
    fn default() -> Self {
        Self {
            data_dir: PathBuf::from("../CB"),
            validate: false,
            ticks: None,
            auto_confirm: false,
            headless: false,
            screenshot: None,
            original_options: Vec::new(),
            help: false,
        }
    }
}

fn parse_command_line(arguments: impl IntoIterator<Item = String>) -> Result<CommandLine> {
    let mut options = CommandLine::default();
    let mut arguments = arguments.into_iter();
    while let Some(argument) = arguments.next() {
        match argument.as_str() {
            "--help" | "-h" => {
                options.help = true;
                return Ok(options);
            }
            "--data" => {
                options.data_dir = PathBuf::from(
                    arguments
                        .next()
                        .ok_or_else(|| EngineError::Usage("--data requires a directory".into()))?,
                )
            }
            "--validate" => options.validate = true,
            "--ticks" => {
                options.ticks = Some(
                    arguments
                        .next()
                        .ok_or_else(|| EngineError::Usage("--ticks requires a count".into()))?
                        .parse::<usize>()
                        .map_err(|_| EngineError::Usage("invalid --ticks count".into()))?,
                )
            }
            "--auto-confirm" => options.auto_confirm = true,
            "--headless" => options.headless = true,
            "--screenshot" => {
                options.screenshot = Some(PathBuf::from(arguments.next().ok_or_else(|| {
                    EngineError::Usage("--screenshot requires a filename".into())
                })?))
            }
            _ if argument.starts_with("--") => {
                return Err(EngineError::Usage(format!("unknown option: {argument}")));
            }
            _ => options.original_options.push(argument),
        }
    }

    if !options.headless && options.ticks.is_some() {
        return Err(EngineError::Usage("--ticks requires --headless".into()));
    }
    if !options.headless && options.auto_confirm {
        return Err(EngineError::Usage(
            "--auto-confirm requires --headless".into(),
        ));
    }
    Ok(options)
}

fn run() -> Result<()> {
    let options = parse_command_line(std::env::args().skip(1))?;
    if options.help {
        print_help();
        return Ok(());
    }
    if options.validate {
        return validate_data(&options.data_dir);
    }
    let mut config = LaunchConfig::parse(options.original_options, &options.data_dir)?;
    if config.export.is_some() {
        let policy_path = config.data_dir.join("SOUND.5");
        if policy_path.is_file() {
            config.apply_policy(InstallationPolicy::parse(&fs::read(policy_path)?)?);
        }
        return export_text(&config);
    }
    let mut engine = Engine::open(config)?;
    if !options.headless {
        run_sdl(&mut engine)?;
    } else if let Some(count) = options.ticks {
        let mut next_input = options.auto_confirm.then_some(InputEvent::Confirm);
        for _ in 0..count {
            let input = next_input.take().into_iter();
            engine.tick(input)?;
            next_input = options.auto_confirm.then_some(InputEvent::Confirm);
            for event in engine.take_events() {
                if options.auto_confirm
                    && let EngineEvent::Choices(ref choices) = event
                {
                    next_input = Some(InputEvent::Choose(choices.len().saturating_sub(1)));
                }
            }
        }
        println!("stopped in scene {}", engine.scene_name());
        let actions: Vec<_> = engine.actions().map(|(label, _, _)| label).collect();
        if !actions.is_empty() {
            println!("active actions: {}", actions.join(", "));
        }
    } else {
        interactive(&mut engine)?;
    }
    if let Some(path) = options.screenshot {
        fs::write(&path, engine.framebuffer().ppm(engine.palette()))?;
        println!("wrote {}", path.display());
    }
    Ok(())
}

fn export_text(config: &LaunchConfig) -> Result<()> {
    let request = config
        .export
        .as_ref()
        .ok_or_else(|| EngineError::Usage("no text export was requested".into()))?;
    let archive = Archive::open(config.data_dir.join("DD1.DAT"))?;
    let translation = captain_bible_engine::config::translation_letter(request.translation)?;
    let mut banks = Vec::new();
    for bank in b"ABCDEFGR" {
        let index = archive.read(&format!("{translation}{}", *bank as char))?;
        let companion = fs::read(config.data_dir.join(format!("DDL{}", *bank as char)))?;
        banks.push(TextBank::parse(*bank, &index, &companion, false)?);
    }
    let data = export_study(&banks, request.mask, config.filter_mature)?;
    fs::write(&request.filename, data)?;
    println!("wrote {}", request.filename.display());
    Ok(())
}

fn interactive(engine: &mut Engine) -> Result<()> {
    println!("Captain Bible Rust engine (logical 320x200 frontend)");
    println!(
        "Enter advances dialogue; use a choice number, action selector, 'study N', or 'quit'."
    );
    loop {
        let status = engine.tick([])?;
        for event in engine.take_events() {
            match event {
                EngineEvent::SceneChanged { scene, entry } => println!("\n[scene {scene} {entry}]"),
                EngineEvent::Dialogue { channel, text } => println!("{channel:?}: {text}"),
                EngineEvent::Choices(choices) => {
                    for (index, choice) in choices.iter().enumerate() {
                        println!("  {}. {choice}", index + 1);
                    }
                }
                EngineEvent::StudyRequested {
                    expected_selector: _,
                    prompt_component,
                } => {
                    println!("[Computer Bible; prompt component {prompt_component:#x}]");
                    let records = engine.available_study_records();
                    if records.is_empty() {
                        println!("  no obtained verses are available");
                    } else {
                        for record in records {
                            println!(
                                "  study {}: {} - {}",
                                record.selector, record.citation, record.verse
                            );
                        }
                    }
                }
                EngineEvent::Music(number) => println!("[music {number}]"),
                EngineEvent::Sound(number) => println!("[effect {number}]"),
                EngineEvent::RestoreRequested => {
                    println!("[restore requested; use F9/quick-load in a graphical frontend]")
                }
                EngineEvent::ExitRequested => return Ok(()),
            }
        }
        if status == EngineStatus::Exited {
            return Ok(());
        }
        if status != EngineStatus::AwaitingInput && engine.actions().next().is_none() {
            continue;
        }
        let actions: Vec<_> = engine
            .actions()
            .map(|(label, _, _)| label.to_owned())
            .collect();
        if !actions.is_empty() {
            println!("actions: {}", actions.join(", "));
        }
        print!("> ");
        io::stdout().flush()?;
        let mut line = String::new();
        if io::stdin().read_line(&mut line)? == 0 {
            return Ok(());
        }
        let line = line.trim();
        let event = if line.is_empty() {
            InputEvent::Confirm
        } else if line.eq_ignore_ascii_case("quit") {
            return Ok(());
        } else if let Some(value) = line.strip_prefix("study ") {
            InputEvent::ApplyStudy(
                value
                    .parse::<u8>()
                    .map_err(|_| EngineError::Usage("study selector must be a byte".into()))?,
            )
        } else if let Ok(choice) = line.parse::<usize>() {
            InputEvent::Choose(choice.saturating_sub(1))
        } else {
            InputEvent::Action(line.to_owned())
        };
        engine.tick([event])?;
    }
}

fn validate_data(data_dir: &Path) -> Result<()> {
    let archive = Archive::open(data_dir.join("DD1.DAT"))?;
    let mut totals = [0usize; 6];
    for entry in archive.entries() {
        let data = archive.extract(entry)?;
        match entry.extension.as_str() {
            "ART" => {
                Art::parse(&data)?;
                totals[0] += 1;
            }
            "PAL" => {
                Palette::parse(&data)?;
                totals[1] += 1;
            }
            "ABT" => {
                Effect::decode(&data)?;
                totals[2] += 1;
            }
            "XMI" => {
                validate_xmi(&data)?;
                totals[3] += 1;
            }
            "MAP" => {
                WorldMap::parse(&data)?;
                totals[4] += 1;
            }
            "BIN" => {
                for region in code_regions(&entry.filename(), data.len()) {
                    let mut position = region.start;
                    while position < region.end {
                        let command = decode(&data[..region.end], position)?;
                        position = command.end;
                    }
                }
                totals[5] += 1;
            }
            _ => {}
        }
    }
    InstallationPolicy::parse(&fs::read(data_dir.join("SOUND.5"))?)?;
    for translation in b"KNRT" {
        let mut record_count = 0usize;
        for bank in b"ABCDEFGR" {
            let index = archive.read(&format!("{}{}", *translation as char, *bank as char))?;
            let companion = fs::read(data_dir.join(format!("DDL{}", *bank as char)))?;
            record_count += TextBank::parse(*bank, &index, &companion, false)?
                .descriptors
                .len();
        }
        if record_count != 319 {
            return Err(EngineError::format(
                "text resources",
                format!(
                    "translation {} has {record_count} records, expected 319",
                    *translation as char
                ),
            ));
        }
    }
    let save_index = data_dir.join("DDGAMES.SV0");
    if save_index.is_file() {
        SaveIndex::parse(&fs::read(save_index)?)?;
    }
    for slot in 1..=9 {
        let path = data_dir.join(format!("DDGAMES.SV{slot}"));
        if path.is_file() {
            SaveImage::parse(&fs::read(path)?)?;
        }
    }
    println!("validated {} archive members", archive.entries().len());
    println!(
        "ART={} PAL={} ABT={} XMI={} MAP={} BIN={}",
        totals[0], totals[1], totals[2], totals[3], totals[4], totals[5]
    );
    Ok(())
}

fn print_help() {
    println!("captain-bible [engine options] [original options] [player-prefix]");
    println!("\nEngine options:");
    println!("  --data DIR          original game-data directory (default ../CB)");
    println!("  --validate          validate all archive resources and exit");
    println!("  --headless          use the terminal or deterministic tick frontend");
    println!("  --ticks N           run N logical ticks without prompting");
    println!("  --auto-confirm      confirm prompts and choose the final dialogue row");
    println!("  --screenshot FILE   write the final framebuffer as a PPM image");
    println!("\nOriginal options: -t -bX -c -idirectory -sXfilename -gXX");
}

fn run_sdl(engine: &mut Engine) -> Result<()> {
    captain_bible_engine::frontend::run_sdl(engine)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn arguments(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| (*value).to_owned()).collect()
    }

    #[test]
    fn command_line_defaults_to_sdl_and_accepts_headless() {
        assert!(!parse_command_line(arguments(&[])).unwrap().headless);
        assert!(
            parse_command_line(arguments(&["--headless"]))
                .unwrap()
                .headless
        );
    }

    #[test]
    fn removed_sdl_option_is_rejected() {
        assert!(parse_command_line(arguments(&["--sdl"])).is_err());
    }

    #[test]
    fn tick_runner_requires_headless_mode() {
        assert!(parse_command_line(arguments(&["--ticks", "1"])).is_err());
        let options =
            parse_command_line(arguments(&["--headless", "--ticks", "1", "--auto-confirm"]))
                .unwrap();
        assert_eq!(options.ticks, Some(1));
        assert!(options.auto_confirm);
    }
}
