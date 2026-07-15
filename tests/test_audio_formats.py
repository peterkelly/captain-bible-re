from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_abt import AbtFormatError, decode_abt, write_wav  # noqa: E402
from extract_dd1 import DD1Archive  # noqa: E402
from inspect_xmi import XmiFormatError, parse_xmi  # noqa: E402


class AudioFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")
        cls.abt_members = [
            cls.archive.extract(entry)
            for entry in cls.archive.entries
            if entry.extension == "ABT"
        ]
        cls.xmi_members = [
            cls.archive.extract(entry)
            for entry in cls.archive.entries
            if entry.extension == "XMI"
        ]

    @classmethod
    def member(cls, filename):
        return cls.archive.extract(cls.archive.matching(filename)[0])

    def test_every_abt_decodes_and_consumes_its_stream(self):
        self.assertEqual(len(self.abt_members), 41)
        decoded = [decode_abt(data) for data in self.abt_members]
        self.assertTrue(all(audio.sample_rate == 9000 for audio in decoded))
        self.assertTrue(all(audio.block_samples == 32 for audio in decoded))
        self.assertTrue(all(audio.codec_id == 2 for audio in decoded))
        self.assertEqual(
            sum(len(audio.samples) for audio in decoded),
            sum(int.from_bytes(data[:2], "little") for data in self.abt_members),
        )

    def test_d003_pcm_matches_qemu_validated_regression(self):
        audio = decode_abt(self.member("D003.ABT"))
        self.assertEqual(len(audio.samples), 9064)
        self.assertEqual(
            sha256(audio.samples).hexdigest(),
            "ca97ad22acf3cc39d078b619168fa026d"
            "eb1606082999bfb8b9a1aac4957422b",
        )

    def test_wav_writer_preserves_pcm_properties(self):
        audio = decode_abt(self.member("D003.ABT"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "d003.wav"
            write_wav(output, audio)
            with wave.open(str(output), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getsampwidth(), 1)
                self.assertEqual(stream.getframerate(), 9000)
                self.assertEqual(stream.getnframes(), 9064)
                self.assertEqual(stream.readframes(9064), audio.samples)

    def test_abt_rejects_truncation_and_trailing_data(self):
        data = self.member("D003.ABT")
        with self.assertRaises(AbtFormatError):
            decode_abt(data[:-1])
        with self.assertRaisesRegex(AbtFormatError, "trailing"):
            decode_abt(data + b"\0")

    def test_every_xmi_has_one_valid_sequence(self):
        self.assertEqual(len(self.xmi_members), 32)
        parsed = [parse_xmi(data) for data in self.xmi_members]
        self.assertTrue(all(xmi.declared_sequences == 1 for xmi in parsed))
        self.assertTrue(all(len(xmi.sequences) == 1 for xmi in parsed))
        self.assertTrue(all(xmi.sequences[0].note_count > 0 for xmi in parsed))

    def test_mus001_xmi_event_regression(self):
        xmi = parse_xmi(self.member("MUS001.XMI"))
        sequence = xmi.sequences[0]
        self.assertEqual(len(sequence.timbres), 12)
        self.assertEqual(sequence.event_count, 446)
        self.assertEqual(sequence.note_count, 432)
        self.assertEqual(sequence.meta_count, 8)
        self.assertEqual(sequence.total_delay, 3016)
        self.assertEqual(sequence.padding, 0)

    def test_xmi_rejects_bad_container_and_missing_end_event(self):
        data = self.member("MUS001.XMI")
        with self.assertRaisesRegex(XmiFormatError, "XDIR"):
            parse_xmi(b"NOPE" + data[4:])
        end_marker = data.rfind(b"\xff\x2f\x00")
        self.assertGreater(end_marker, 0)
        damaged = data[:end_marker] + b"\xff\x01\x00" + data[end_marker + 3 :]
        with self.assertRaisesRegex(XmiFormatError, "no end-of-track"):
            parse_xmi(damaged)


if __name__ == "__main__":
    unittest.main()
