import os

# MYSQL
mysql = {
    "DB_HOSTNAME": os.environ.get("MYSQL_DB_HOSTNAME", ""),
    "DB_USER": os.environ.get("MYSQL_DB_USER", ""),
    "DB_PASSWORD": os.environ.get("MYSQL_DB_PASSWORD", ""),
    "DB_NAME": os.environ.get("MYSQL_DB_NAME", ""),
    "DB_PORT": int(os.environ.get("MYSQL_DB_PORT", 3306))
}

# MONGODB
mongodb = {
    "DB_HOSTNAME": os.environ.get("MONGODB_DB_HOSTNAME", ""),
    "DB_USER": os.environ.get("MONGODB_DB_USER", ""),
    "DB_PASSWORD": os.environ.get("MONGODB_DB_PASSWORD", ""),
    "DB_NAME": os.environ.get("MONGODB_DB_NAME", ""),
    "DB_PORT": int(os.environ.get("MONGODB_DB_PORT", 27017))
}

# UTILITS
utilits = {
    "HOST": os.environ.get("UTILITS_HOST", ""),
    "PATH_DIR": os.environ.get("UTILITS_PATH_DIR", "/api/controller"),
    "PATH_SCHEMA": os.environ.get("UTILITS_PATH_SCHEMA", "/api/schema")
}

# AWS
aws = {
    "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", ""),
    "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
    "TOPIC_ARN": os.environ.get("AWS_TOPIC_ARN", "")
}

# JWT
jwt = {
    "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY", ""),
    "JWT_ACCESS_TOKEN_EXPIRES": int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 2629743))
}

# KING HOST
kinghost = {
    "AUTH": os.environ.get("KINGHOST_AUTH", "")
}

# MERCADOPAGO
mercadopago = {
    "CLIENT_ID": os.environ.get("MERCADOPAGO_CLIENT_ID", ""),
    "CLIENT_SECRET": os.environ.get("MERCADOPAGO_CLIENT_SECRET", ""),
    "PUBLIC_KEY": os.environ.get("MERCADOPAGO_PUBLIC_KEY", ""),
    "ACCESS_TOKEN": os.environ.get("MERCADOPAGO_ACCESS_TOKEN", ""),
    "BACK_URL": os.environ.get("MERCADOPAGO_BACK_URL", ""),
    "WEBHOOK_SECRET": os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "")
}

# SMTP
smtp = {
    "HOST": os.environ.get("SMTP_HOST", ""),
    "PORT": int(os.environ.get("SMTP_PORT", 465)),
    "FROM": os.environ.get("SMTP_FROM", ""),
    "PASS": os.environ.get("SMTP_PASS", "")
}

# CRYPTO
crypto = {
    "KEY_BYTE": os.environ.get("CRYPTO_KEY_BYTE", "").encode(),
    "IV_BYTE": os.environ.get("CRYPTO_IV_BYTE", "").encode(),
    "KEY": os.environ.get("CRYPTO_KEY", "")
}

# SENTRY
sentry = {
    "DSN": os.environ.get("SENTRY_DSN", "")
}

# FIREBASE
firebase = {
    "API_KEY": os.environ.get("FIREBASE_API_KEY", "")
}
