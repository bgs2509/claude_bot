.PHONY: run install clean help vps logs-vps

help:  ## Показать справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

run:  ## Запустить бота
	uv run ai-steward

install:  ## Установить зависимости
	uv sync

vps:  ## Установить и перезапустить systemd-сервис
	sudo cp ai-steward.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable ai-steward
	sudo systemctl restart ai-steward

logs-vps:  ## Логи systemd-сервиса (follow)
	sudo journalctl -u ai-steward -f

clean:  ## Удалить кэш и .venv
	rm -rf .venv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
