"""Push-to-talk operator station using an OpenAI-compatible transcription API."""

from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import wave

import numpy as np
import rclpy
from rclpy.node import Node
import sounddevice as sd
from std_msgs.msg import String

from .ai_gateway import create_ai_client, load_ai_settings


class VoiceOperatorNode(Node):
    def __init__(self) -> None:
        super().__init__("voice_operator")
        self.ai = load_ai_settings()
        self.declare_parameter("record_seconds", 7.0)
        self.declare_parameter("sample_rate", 16_000)
        self.declare_parameter(
            "transcription_model", self.ai.transcription_model
        )
        self.publisher = self.create_publisher(String, "/hazard/command_text", 10)
        self.client = create_ai_client(self.ai)
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        self.get_logger().info(
            f"press Enter to record; provider={self.ai.provider}; "
            f"model={self.ai.transcription_model}"
        )

    def _record_loop(self) -> None:
        while rclpy.ok():
            try:
                input("voice-operator [Enter to record]> ")
            except EOFError:
                return
            try:
                text = self._record_and_transcribe()
            except Exception as exc:
                self.get_logger().error(f"voice command failed: {exc}")
                continue
            message = String()
            message.data = text
            self.publisher.publish(message)
            self.get_logger().info(f"transcribed: {text}")

    def _record_and_transcribe(self) -> str:
        seconds = float(self.get_parameter("record_seconds").value)
        sample_rate = int(self.get_parameter("sample_rate").value)
        model = str(self.get_parameter("transcription_model").value)
        self.get_logger().info(f"recording for {seconds:.1f}s")
        audio = sd.rec(
            int(seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        pcm = np.clip(audio[:, 0], -1.0, 1.0)
        pcm = (pcm * 32767.0).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = handle.name
        try:
            with wave.open(path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm.tobytes())
            with open(path, "rb") as audio_file:
                result = self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    prompt="ROS2, LiDAR, 向前, 左转, 右转, 墙壁, 岔路口, 安全地点",
                )
        finally:
            Path(path).unlink()

        text = result.text.strip()
        if not text:
            raise RuntimeError("transcription was empty")
        return text


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = VoiceOperatorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

