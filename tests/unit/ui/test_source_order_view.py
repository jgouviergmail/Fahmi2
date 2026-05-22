"""Smoke tests du widget ``SourceOrderView`` (double liste ordre/exclusion)."""

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.ui.widgets.source_order_view import SourceOrderView


def _src(name: str, kind: SourceKind = SourceKind.VIDEO) -> InputSource:
    return InputSource(kind=kind, location=name)


def test_populate_and_getters(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    available = [_src("a.mp4"), _src("b.mp4"), _src("c.mp4")]
    view.populate(available, source_order=("c.mp4", "a.mp4"), excluded=("b.mp4",))
    assert view.source_order() == ("c.mp4", "a.mp4")
    assert view.excluded_sources() == ("b.mp4",)


def test_exclude_and_reinclude_all(qtbot: QtBot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    view.populate([_src("a.mp4"), _src("b.mp4")], source_order=(), excluded=())
    view.exclude_key("a.mp4")
    assert "a.mp4" in view.excluded_sources()
    assert "a.mp4" not in view.source_order()
    view.reinclude_all()
    assert view.excluded_sources() == ()
    assert set(view.source_order()) == {"a.mp4", "b.mp4"}
