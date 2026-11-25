"""image-against-form experiment: the network and the mirror augmentation. Every test here needs torch and is skipped when torch is not installed."""
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "spikes"))

from imagem_formulario import labels, net  # noqa: E402


def test_mirroring_flips_the_picture_and_swaps_left_and_right_in_the_label():
    x = torch.zeros(2, 3, 200, 140)
    x[0, :, 50, 10] = 1.0  # a mark near the left edge of the picture
    y = torch.tensor([labels.encode_attrs(__import__("para_triage.consistency.schema", fromlist=["Attrs"]).Attrs(lower_left=3, lower_right=0, upper_left=1, upper_right=2, wheelchair="yes", prosthesis="no"), 2)] * 2)
    xm, ym = net.mirror_batch(x, y)
    assert xm[0, 0, 50, 140 - 1 - 10] == 1.0 and xm[0, 0, 50, 10] == 0.0  # the mark moved to the right edge
    assert ym[0].tolist() == [y[0][1], y[0][0], y[0][3], y[0][2], y[0][4], y[0][5]]
    assert torch.equal(net.mirror_batch(*net.mirror_batch(x, y))[0], x) and torch.equal(net.mirror_batch(*net.mirror_batch(x, y))[1], y)


def test_the_network_has_about_a_million_parameters_and_six_heads_of_the_right_size():
    model = net.SmallNet()
    assert 5e5 < net.parameter_count(model) < 2e6
    out = model(torch.zeros(2, 3, 200, 140))
    assert [o.shape[1] for o in out] == [labels.N_CLASSES[h] for h in labels.HEADS] == [5, 5, 4, 4, 3, 3]


def test_an_ignored_label_takes_no_loss():
    logits = [torch.randn(4, labels.N_CLASSES[h], requires_grad=True) for h in labels.HEADS]
    y = torch.zeros(4, 6, dtype=torch.long)
    y[:, 4:] = labels.IGNORE
    loss = net.loss_fn(logits, y)
    loss.backward()
    assert logits[4].grad.abs().sum() == 0 and logits[5].grad.abs().sum() == 0 and logits[0].grad.abs().sum() > 0


def test_the_flipped_reading_is_the_reading_of_the_reflected_picture_with_the_sides_put_back():
    torch.manual_seed(0)
    model = net.SmallNet()
    x = (np.random.RandomState(0).rand(3, 200, 140, 3) * 255).astype(np.uint8)
    plain = net.predict(model, x[:, :, ::-1].copy())  # the reflected pictures, read as they are
    flipped = net.predict(model, x, flip=True)        # the same reflection done inside predict
    for j in range(6):
        assert np.allclose(flipped[j], plain[labels.SWAP_INDEX[j]], atol=1e-5)


def test_a_few_training_steps_lower_the_loss_on_an_easy_task():
    """The network can learn: a bright left half versus a bright right half, read by the lower_left head."""
    torch.manual_seed(1)
    model = net.SmallNet()
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    x = torch.zeros(32, 3, 200, 140)
    y = torch.full((32, 6), labels.IGNORE, dtype=torch.long)
    y[:, :4] = 0
    x[:16, :, :, :70] = 0.4
    y[:16, 0] = 1
    x[16:, :, :, 70:] = 0.4
    first = last = None
    for step in range(25):
        loss = net.loss_fn(model(x), y)
        opt.zero_grad()
        loss.backward()
        opt.step()
        first = float(loss) if first is None else first
        last = float(loss)
    assert last < 0.6 * first
