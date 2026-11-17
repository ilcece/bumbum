import re


def structure_state(cursor, columns, unique_keys, foreign_keys, *, generated=None, defaults=None):
    tables = sorted({table for table, _ in columns})
    placeholders = ','.join(['%s'] * len(tables))
    cursor.execute(
        'SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,EXTRA,GENERATION_EXPRESSION,COLUMN_DEFAULT '
        'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() '
        f'AND TABLE_NAME IN ({placeholders})', tables,
    )
    actual_columns = {
        (table, name): (kind, nullable, extra, expression, column_default)
        for table, name, kind, nullable, extra, expression, column_default in cursor.fetchall()
    }
    if not actual_columns:
        return 'missing'
    if {key: value[:3] for key, value in actual_columns.items()} != columns:
        return 'unknown'
    expected_generated = generated or {}
    expected_defaults = defaults or {}
    for key, value in actual_columns.items():
        expression = ''.join(character for character in (value[3] or '').lower()
                             if not character.isspace() and character != '`')
        while expression.startswith('(') and expression.endswith(')'):
            expression = expression[1:-1]
        if expression != expected_generated.get(key, ''):
            return 'unknown'
        expected_default = expected_defaults.get(key)
        actual_default = value[4]
        if isinstance(expected_default, str):
            if not isinstance(actual_default, str) or actual_default.strip().lower() != expected_default.lower():
                return 'unknown'
        elif actual_default != expected_default:
            return 'unknown'

    cursor.execute(
        'SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SEQ_IN_INDEX,SUB_PART '
        'FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() '
        f'AND TABLE_NAME IN ({placeholders}) ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX', tables,
    )
    indexes = {}
    for table, name, non_unique, column, position, prefix in cursor.fetchall():
        indexes.setdefault((table, name), []).append((non_unique, column, position, prefix))
    actual_unique = {
        key: values for key, values in indexes.items() if any(value[0] == 0 for value in values)
    }
    expected_unique = {
        key: [(0, name, position, None) for position, name in enumerate(names, 1)]
        for key, names in unique_keys.items()
    }
    if actual_unique != expected_unique:
        return 'unknown'

    cursor.execute(
        'SELECT k.TABLE_NAME,k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_NAME,'
        'k.REFERENCED_COLUMN_NAME,k.ORDINAL_POSITION,r.DELETE_RULE,r.UPDATE_RULE '
        'FROM information_schema.KEY_COLUMN_USAGE k '
        'JOIN information_schema.REFERENTIAL_CONSTRAINTS r '
        'ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.TABLE_NAME=k.TABLE_NAME '
        'AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME '
        'WHERE k.TABLE_SCHEMA=DATABASE() AND k.REFERENCED_TABLE_SCHEMA=DATABASE() '
        f'AND k.TABLE_NAME IN ({placeholders})', tables,
    )
    references = {
        (*record[:6], *('RESTRICT' if rule == 'NO ACTION' else rule for rule in record[6:]))
        for record in cursor.fetchall()
    }
    if references != foreign_keys:
        return 'unknown'

    null_defaults = {}
    for key, (_, nullable, _) in columns.items():
        if nullable == 'YES' and key not in expected_generated and expected_defaults.get(key) is None:
            table, name = key
            null_defaults.setdefault(table, []).append(name)
    # COLUMN_DEFAULT不能区分NULL默认值和缺省；后者实测会令省略字段的写入报1364。
    for table, names in null_defaults.items():
        cursor.execute('SHOW CREATE TABLE `' + table.replace('`', '``') + '`')
        definition = cursor.fetchone()[1]
        declarations = definition.splitlines()
        for name in names:
            escaped = re.escape(name)
            column_start = rf'^\s*(?:`{escaped}`|"{escaped}"|{escaped})\s+'
            declaration = next((line for line in declarations if re.match(column_start, line)), '')
            before_comment = re.split(r'\s+COMMENT\s+', declaration, maxsplit=1, flags=re.IGNORECASE)[0]
            if not re.search(r'\bDEFAULT\s+NULL\b', before_comment, flags=re.IGNORECASE):
                return 'unknown'
    return 'ready'
