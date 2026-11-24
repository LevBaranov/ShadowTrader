FROM python:3.12-slim

WORKDIR /app

# --- Корневые сертификаты Минцифры (Russian Trusted CA) ---
# opensource.tbank.ru (PyPI-индекс пакета t-tech-investments) отдаёт
# сертификат, выпущенный промежуточным CA Минцифры. Без этих корневых
# сертификатов pip падает с SSL CERTIFICATE_VERIFY_FAILED.
# Источник: https://www.gosuslugi.ru/crt
# (файлы получены по AIA-ссылкам цепочки: nuc-cdp.digital.gov.ru).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY certs/russian-trusted-root-ca.crt certs/russian-trusted-sub-ca.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# pip проверяет TLS по собственному бандлу, а не системному хранилищу,
# поэтому явно указываем ему системный бандл с добавленными CA.
# SSL_CERT_FILE / REQUESTS_CA_BUNDLE покрывают рантайм (urllib, requests).
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# httpx и подобные по умолчанию берут CA из пакета certifi, который ставится
# вместе с зависимостями, поэтому добавляем CA Минцифры в его бандл уже
# после установки зависимостей. Проверка — офлайн: бандл должен грузиться
# в SSL-контекст (ловит битую склейку PEM) и содержать наши сертификаты.
# Сетевой smoke-тест к индексу Т-Банка здесь не делаем: хост отвечает
# медленно/нестабильно из CI-раннеров, а успешный pip install выше —
# уже достаточное доказательство рабочего TLS.
RUN { echo; cat /usr/local/share/ca-certificates/russian-trusted-root-ca.crt \
        /usr/local/share/ca-certificates/russian-trusted-sub-ca.crt; } \
    >> "$(python -c 'import certifi; print(certifi.where())')" \
    && python -c "import certifi, ssl; bundle = open(certifi.where(), 'rb').read(); ssl.create_default_context(cafile=certifi.where()); assert open('/usr/local/share/ca-certificates/russian-trusted-root-ca.crt', 'rb').read().strip() in bundle and open('/usr/local/share/ca-certificates/russian-trusted-sub-ca.crt', 'rb').read().strip() in bundle; print('certifi bundle OK, MinCifry CAs present')"

COPY . .

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]