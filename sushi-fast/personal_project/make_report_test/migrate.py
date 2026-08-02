from .db_repository import migrate, schema_summary


def main() -> None:
    migrate()
    print("기존 personal_project.db 마이그레이션 완료")
    for table, columns in schema_summary().items():
        print(f"- {table}: {', '.join(columns)}")


if __name__ == "__main__":
    main()

