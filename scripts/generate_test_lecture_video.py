from __future__ import annotations

from pathlib import Path

import pyttsx3
from moviepy import AudioFileClip, ImageClip
from PIL import Image, ImageDraw, ImageFont


def _draw_slide(slide_path: Path) -> None:
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), (20, 42, 84))
    draw = ImageDraw.Draw(image)

    try:
        title_font = ImageFont.truetype("arial.ttf", 58)
        body_font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 120)], fill=(8, 24, 52))
    draw.text((60, 28), "V2AI Test Lecture: Neural Networks", fill=(255, 255, 255), font=title_font)

    bullet_lines = [
        "1. A neural network maps inputs to outputs using weighted layers.",
        "2. During training, backpropagation updates weights to reduce loss.",
        "3. Learning rate controls the size of each optimization step.",
        "4. Overfitting happens when a model memorizes training data.",
        "5. Regularization and validation help improve generalization.",
    ]

    y_pos = 170
    for line in bullet_lines:
        draw.text((90, y_pos), f"- {line}", fill=(240, 245, 255), font=body_font)
        y_pos += 86

    draw.rectangle([(0, height - 74), (width, height)], fill=(8, 24, 52))
    draw.text(
        (60, height - 56),
        "Generated for end-to-end upload, transcript, Q&A and citation test",
        fill=(173, 214, 255),
        font=body_font,
    )

    image.save(slide_path)


def _generate_audio(audio_path: Path) -> None:
    lecture_text = (
        "Welcome to this short lecture on neural networks. "
        "A neural network is a model that learns patterns from data by stacking layers of neurons. "
        "Each layer applies weights and activation functions to transform information. "
        "During training, we compute a loss value and run back propagation to update parameters. "
        "The learning rate controls how big each update step is during optimization. "
        "If the model performs well on training data but poorly on new data, it is overfitting. "
        "To reduce overfitting, we can use validation, dropout, and regularization. "
        "In practical machine learning systems, we monitor performance "
        "and retrain models when needed."
    )

    engine = pyttsx3.init()
    engine.setProperty("rate", 162)
    engine.save_to_file(lecture_text, str(audio_path))
    engine.runAndWait()


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "artifacts" / "sample_lecture"
    output_dir.mkdir(parents=True, exist_ok=True)

    slide_path = output_dir / "test_slide.png"
    audio_path = output_dir / "test_lecture_audio.wav"
    video_path = output_dir / "test_lecture_v2ai.mp4"

    _draw_slide(slide_path)
    _generate_audio(audio_path)

    audio_clip = AudioFileClip(str(audio_path))
    video_clip = (
        ImageClip(str(slide_path))
        .with_duration(audio_clip.duration)
        .with_audio(audio_clip)
    )
    video_clip.write_videofile(
        str(video_path),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    audio_clip.close()
    video_clip.close()

    print(video_path)


if __name__ == "__main__":
    main()
