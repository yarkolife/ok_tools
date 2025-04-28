FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    default-jre \
    pdftk-java \
    postgresql-client \
    curl \
    autopoint \
    texinfo \
    gettext \
    && curl -LO http://ftp.gnu.org/pub/gnu/gettext/gettext-0.21.tar.gz \
    && tar -xvzf gettext-0.21.tar.gz \
    && cd gettext-0.21 \
    && ./configure --with-included-gettext \
    && make -j"$(nproc)" \
    && make install \
    && echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf \
    && ldconfig \
    && cd .. && rm -rf gettext-0.21 gettext-0.21.tar.gz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app
COPY docker.cfg /app/docker.cfg
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["/entrypoint.sh"]
