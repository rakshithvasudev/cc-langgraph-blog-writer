"""Tests for graph nodes."""

import pytest

from research_agent.graph.nodes import _enforce_writing_style, _parse_json_response


class TestEnforceWritingStyle:
    """Tests for the writing style enforcement function."""

    def test_removes_em_dashes(self):
        """Test that em dashes are replaced with commas."""
        text = "The study -- conducted over three years -- revealed findings."
        result = _enforce_writing_style(text)
        assert "--" not in result
        assert ", conducted over three years, revealed" in result

    def test_removes_unicode_em_dash(self):
        """Test that Unicode em dashes are replaced."""
        text = "The study—conducted over time—showed results."
        result = _enforce_writing_style(text)
        assert "—" not in result

    def test_removes_unicode_en_dash(self):
        """Test that Unicode en dashes are replaced."""
        text = "The study–conducted over time–showed results."
        result = _enforce_writing_style(text)
        assert "–" not in result

    def test_fixes_delve_into(self):
        """Test that 'delve into' is replaced with 'explore'."""
        text = "Let's delve into this topic."
        result = _enforce_writing_style(text)
        assert "delve into" not in result.lower()
        assert "explore" in result.lower()

    def test_fixes_leverage(self):
        """Test that 'leverage' is replaced with 'use'."""
        text = "We can leverage this technology."
        result = _enforce_writing_style(text)
        assert "leverage" not in result.lower()
        assert "use" in result.lower()

    def test_fixes_in_todays_world(self):
        """Test that 'In today's world' is fixed."""
        text = "In today's world, technology is everywhere."
        result = _enforce_writing_style(text)
        assert "In today's world" not in result

    def test_removes_in_conclusion(self):
        """Test that 'In conclusion,' is removed."""
        text = "In conclusion, the results were positive."
        result = _enforce_writing_style(text)
        assert "In conclusion," not in result

    def test_cleans_double_spaces(self):
        """Test that double spaces are cleaned."""
        text = "This  has   multiple  spaces."
        result = _enforce_writing_style(text)
        assert "  " not in result


class TestParseJsonResponse:
    """Tests for JSON parsing from LLM responses."""

    def test_parses_direct_json(self):
        """Test parsing direct JSON."""
        content = '{"key": "value"}'
        result = _parse_json_response(content)
        assert result == {"key": "value"}

    def test_parses_json_array(self):
        """Test parsing JSON array."""
        content = '[{"a": 1}, {"b": 2}]'
        result = _parse_json_response(content)
        assert result == [{"a": 1}, {"b": 2}]

    def test_parses_json_in_markdown(self):
        """Test parsing JSON from markdown code block."""
        content = """Here's the response:
```json
{"key": "value"}
```
"""
        result = _parse_json_response(content)
        assert result == {"key": "value"}

    def test_parses_json_without_json_marker(self):
        """Test parsing JSON from code block without 'json' marker."""
        content = """Here's the response:
```
{"key": "value"}
```
"""
        result = _parse_json_response(content)
        assert result == {"key": "value"}

    def test_parses_embedded_json_object(self):
        """Test parsing JSON embedded in text."""
        content = 'Some text before {"key": "value"} and after.'
        result = _parse_json_response(content)
        assert result == {"key": "value"}

    def test_parses_embedded_json_array(self):
        """Test parsing array embedded in text."""
        content = 'Some text [{"a": 1}] and more.'
        result = _parse_json_response(content)
        assert result == [{"a": 1}]

    def test_raises_on_invalid_json(self):
        """Test that invalid JSON raises an error."""
        content = "This is not JSON at all."
        with pytest.raises(Exception):
            _parse_json_response(content)
