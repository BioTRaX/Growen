from services.logging.ctx_logger import clean_logs


def main() -> int:
    clean_logs()
    print("crawl logs cleaned")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
