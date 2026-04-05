import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skill_normalize import normalize_display, strip_parenthetical_versions, to_slug


def test_normalize_display():
    assert normalize_display("  Foo BAR  ") == "foo bar"


def test_strip_parenthetical():
    assert strip_parenthetical_versions("Python (3.11)") == "Python"
    assert strip_parenthetical_versions("React (v18) hooks") == "React hooks"


def test_to_slug():
    assert to_slug("JavaScript") == "javascript"
    assert to_slug("React (v18)") == "react"
    assert to_slug("C++") == "c++"
    assert to_slug("c++") == "c++"
    assert to_slug("C#") == "c#"
    assert to_slug("F#") == "f#"
    assert to_slug(".NET") == ".net"
    assert to_slug("Node.js") == "node.js"
    assert to_slug("ASP.NET Core") == "asp.net_core"
    assert to_slug("foo-bar baz") == "foo-bar_baz"
