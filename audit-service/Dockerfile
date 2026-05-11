FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir $(python -c "import tomllib as t; print(' '.join(d.replace(' ','') for d in t.load(open('pyproject.toml','rb'))['project']['dependencies']))") 2>/dev/null || true

COPY . .

RUN python manage.py migrate --noinput 2>/dev/null || true

EXPOSE 8004

CMD ["daphne", "-b", "0.0.0.0", "-p", "8004", "config.asgi:application"]
