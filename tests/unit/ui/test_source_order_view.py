"""Smoke tests du widget ``SourceOrderView`` (double liste ordre/exclusion)."""

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.ui.widgets.source_order_view import SourceOrderView


def _src(name: str, kind: SourceKind = SourceKind.VIDEO) -> InputSource:
    return InputSource(kind=kind, location=name)


def test_order_note_hidden_by_default(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    # ``isHidden`` reflète l'état explicite, indépendamment de l'affichage du parent.
    assert view._order_note.isHidden() is True  # noqa: SLF001


def test_set_order_irrelevant_toggles_note(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    view.set_order_irrelevant(True)
    assert view._order_note.isHidden() is False  # noqa: SLF001
    view.set_order_irrelevant(False)
    assert view._order_note.isHidden() is True  # noqa: SLF001


def test_populate_and_getters(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    available = [_src("a.mp4"), _src("b.mp4"), _src("c.mp4")]
    view.populate(
        available,
        included=("c.mp4", "a.mp4"),
        excluded=("b.mp4",),
        known={"a.mp4", "b.mp4", "c.mp4"},
    )
    assert view.source_order() == ("c.mp4", "a.mp4")
    assert view.excluded_sources() == ("b.mp4",)


def test_case_slides_cochable_uniquement_video_youtube(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    sources = [
        _src("a.mp4", SourceKind.VIDEO),
        _src("b.mp3", SourceKind.AUDIO),
        _src("https://youtu.be/x", SourceKind.YOUTUBE),
        _src("c.pdf", SourceKind.DOCUMENT),
    ]
    view.populate(
        sources,
        included=("a.mp4", "b.mp3", "https://youtu.be/x", "c.pdf"),
        excluded=(),
        known=set(),
        slides=("a.mp4",),
    )
    assert view.slides_sources() == ("a.mp4",)
    video_item = view._included.item(0)  # noqa: SLF001
    audio_item = view._included.item(1)  # noqa: SLF001
    document_item = view._included.item(3)  # noqa: SLF001
    assert video_item is not None and audio_item is not None
    assert document_item is not None
    assert video_item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert not (audio_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert not (document_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert video_item.checkState() == Qt.CheckState.Checked


def test_cocher_une_video_l_ajoute_aux_slides(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    view.populate(
        [_src("https://youtu.be/x", SourceKind.YOUTUBE)],
        included=("https://youtu.be/x",),
        excluded=(),
        known=set(),
        slides=(),
    )
    assert view.slides_sources() == ()
    item = view._included.item(0)  # noqa: SLF001
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked)
    assert view.slides_sources() == ("https://youtu.be/x",)


def test_exclude_and_reinclude_all(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    view.populate(
        [_src("a.mp4"), _src("b.mp4")],
        included=("a.mp4", "b.mp4"),
        excluded=(),
        known={"a.mp4", "b.mp4"},
    )
    view.exclude_key("a.mp4")
    assert "a.mp4" in view.excluded_sources()
    assert "a.mp4" not in view.source_order()
    view.reinclude_all()
    assert view.excluded_sources() == ()
    assert set(view.source_order()) == {"a.mp4", "b.mp4"}
