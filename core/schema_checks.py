def structure_state(cursor, columns, unique_keys, foreign_keys, *, generated=None):
    tables = sorted({table for table, _ in columns})
    placeholders = ','.join(['%s'] * len(tables))
    cursor.execute(
        'SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,EXTRA,GENERATION_EXPRESSION '
        'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() '
        f'AND TABLE_NAME IN ({placeholders})', tables,
    )
    actual_columns = {
        (table, name): (kind, nullable, extra, expression)
        for table, name, kind, nullable, extra, expression in cursor.fetchall()
    }
    if not actual_columns:
        return 'missing'
    if {key: value[:3] for key, value in actual_columns.items()} != columns:
        return 'unknown'
    expected_generated = generated or {}
    for key, value in actual_columns.items():
        expression = ''.join(character for character in (value[3] or '').lower()
                             if not character.isspace() and character != '`')
        while expression.startswith('(') and expression.endswith(')'):
            expression = expression[1:-1]
        if expression != expected_generated.get(key, ''):
            return 'unknown'

    cursor.execute(
        'SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SEQ_IN_INDEX,SUB_PART '
        'FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() '
        f'AND TABLE_NAME IN ({placeholders}) ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX', tables,
    )
    indexes = {}
    for table, name, non_unique, column, position, prefix in cursor.fetchall():
        indexes.setdefault((table, name), []).append((non_unique, column, position, prefix))
    for key, names in unique_keys.items():
        expected = [(0, name, position, None) for position, name in enumerate(names, 1)]
        if indexes.get(key) != expected:
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
    return 'ready' if references == foreign_keys else 'unknown'
