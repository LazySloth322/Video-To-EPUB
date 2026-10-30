import numpy as np
from PIL import Image

from video_to_epub.images import (
    SlideChangeDetector,
    compute_change_fraction,
    resize_grayscale,
)


def test_compute_change_fraction_identical():
    a = np.zeros((10, 10), dtype=np.uint8)
    assert compute_change_fraction(a, a, pixel_diff_threshold=12) == 0.0


def test_compute_change_fraction_all_changed():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = np.full((10, 10), 255, dtype=np.uint8)
    assert compute_change_fraction(a, b, pixel_diff_threshold=12) == 1.0


def test_compute_change_fraction_partial():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = a.copy()
    b[:5, :] = 255
    fraction = compute_change_fraction(a, b, pixel_diff_threshold=12)
    assert abs(fraction - 0.5) < 1e-9


def test_resize_grayscale_establishes_target_size():
    image = Image.new("RGB", (100, 50), color="white")
    array, target_size = resize_grayscale(image, resize_width=50)
    assert target_size == (50, 25)
    assert array.shape == (25, 50)
    assert array.dtype == np.uint8


def test_detector_saves_first_frame_and_ignores_unchanged():
    detector = SlideChangeDetector(
        pixel_diff_threshold=12,
        change_threshold=0.02,
        confirm_samples=1,
        debounce_seconds=0.0,
        save_first=True,
    )

    a = np.zeros((20, 30), dtype=np.uint8)

    first = detector.process(a, timestamp=0.0)
    assert first.save is True
    assert first.index == 1

    second = detector.process(a, timestamp=5.0)
    assert second.save is False


def test_detector_saves_significant_change():
    detector = SlideChangeDetector(
        pixel_diff_threshold=12,
        change_threshold=0.02,
        confirm_samples=1,
        debounce_seconds=0.0,
        save_first=True,
    )

    a = np.zeros((20, 30), dtype=np.uint8)
    b = np.full((20, 30), 255, dtype=np.uint8)

    assert detector.process(a, 0.0).save is True
    changed = detector.process(b, 5.0)
    assert changed.save is True
    assert changed.index == 2


def test_detector_confirm_samples_requires_persistence():
    detector = SlideChangeDetector(
        pixel_diff_threshold=12,
        change_threshold=0.02,
        confirm_samples=2,
        debounce_seconds=0.0,
        save_first=True,
    )

    a = np.zeros((20, 30), dtype=np.uint8)
    b = np.full((20, 30), 255, dtype=np.uint8)

    assert detector.process(a, 0.0).save is True

    first_change = detector.process(b, 5.0)
    assert first_change.save is False

    second_change = detector.process(b, 10.0)
    assert second_change.save is True
    assert second_change.index == 2


def test_detector_debounce_delays_but_does_not_drop_persistent_change():
    detector = SlideChangeDetector(
        pixel_diff_threshold=12,
        change_threshold=0.02,
        confirm_samples=1,
        debounce_seconds=5.0,
        save_first=True,
    )

    a = np.zeros((20, 30), dtype=np.uint8)
    b = np.full((20, 30), 255, dtype=np.uint8)

    assert detector.process(a, 0.0).save is True

    early = detector.process(b, 2.0)
    assert early.save is False

    later = detector.process(b, 6.0)
    assert later.save is True
    assert later.index == 2


def test_detector_transient_change_within_debounce_is_ignored():
    detector = SlideChangeDetector(
        pixel_diff_threshold=12,
        change_threshold=0.02,
        confirm_samples=1,
        debounce_seconds=5.0,
        save_first=True,
    )

    a = np.zeros((20, 30), dtype=np.uint8)
    b = np.full((20, 30), 255, dtype=np.uint8)

    assert detector.process(a, 0.0).save is True
    assert detector.process(b, 2.0).save is False
    assert detector.process(a, 4.0).save is False
    assert detector.process(a, 6.0).save is False