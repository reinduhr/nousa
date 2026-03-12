from src.models import Lists

"""
def test_can_create_list(db_session):
    new_list = Lists(list_name="TestList")
    db_session.add(new_list)
    db_session.commit()
    db_session.refresh(new_list)

    assert new_list.list_id is not None
    assert new_list.list_name == "TestList"


def test_tables_created(test_engine):
    from sqlalchemy import inspect

    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())

    expected = {
        'AuditLogEntry', 
        'Series', 
        'Episodes', 
        'JellyfinRecommendation', 
        'ListEntries', 
        'Lists', 
        'SeriesArchive'
    }

    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"
"""