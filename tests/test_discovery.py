from brimley.discovery.scanner import Scanner


def test_scanner_rejects_reserved_function_name(tmp_path):
	f = tmp_path / "bad.sql"
	f.write_text(
		"""/*
---
name: exit
type: sql_function
return_shape: void
---
*/
SELECT 1;
"""
	)

	result = Scanner(tmp_path).scan()

	assert len(result.functions) == 0
	assert any(d.error_code == "ERR_RESERVED_NAME" for d in result.diagnostics)


def test_scanner_assigns_canonical_id_to_discovered_items(tmp_path):
	f = tmp_path / "logic.py"
	f.write_text(
		"""from brimley import function

@function
def hello(name: str) -> str:
	return name
"""
	)

	result = Scanner(tmp_path).scan()

	assert len(result.functions) == 1
	func = result.functions[0]
	assert func.canonical_id is not None
	assert func.canonical_id == "function:logic.py:hello"


def test_scanner_warns_on_name_proximity(tmp_path):
	(tmp_path / "a.sql").write_text(
		"""/*
---
name: get_user
type: sql_function
return_shape: void
---
*/
SELECT 1;
"""
	)
	(tmp_path / "b.sql").write_text(
		"""/*
---
name: get-user
type: sql_function
return_shape: void
---
*/
SELECT 1;
"""
	)

	result = Scanner(tmp_path).scan()

	assert len(result.functions) == 2
	proximity = [d for d in result.diagnostics if d.error_code == "ERR_NAME_PROXIMITY"]
	assert proximity
	assert all(d.severity == "warning" for d in proximity)
