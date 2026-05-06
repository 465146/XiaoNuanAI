-- 小暖 CBT 数据库建表脚本
-- 在 Railway MySQL 的 Query 界面中逐段执行
-- 或通过 MySQL 命令行：mysql -h <host> -u <user> -p < schema.sql

CREATE DATABASE IF NOT EXISTS cbt_xiaonuan DEFAULT CHARACTER SET utf8mb4;
USE cbt_xiaonuan;

-- 1. 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL DEFAULT '',
    email_verified TINYINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 对话记录
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 每日情绪分数
CREATE TABLE IF NOT EXISTS daily_scores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    date DATE NOT NULL,
    score FLOAT NOT NULL DEFAULT 0,
    note TEXT,
    UNIQUE KEY uk_user_date (user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. PHQ-9 测试记录
CREATE TABLE IF NOT EXISTS phq9_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    total_score INT NOT NULL,
    severity VARCHAR(30) NOT NULL,
    q9_score INT NOT NULL DEFAULT 0,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 情绪日记
CREATE TABLE IF NOT EXISTS diary_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    date DATE NOT NULL,
    content TEXT NOT NULL,
    mood VARCHAR(50) NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_date (user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 微信 bot 凭据
CREATE TABLE IF NOT EXISTS wechat_bots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    bot_token TEXT NOT NULL,
    bot_id VARCHAR(255) NOT NULL,
    wechat_user_id VARCHAR(255) NOT NULL DEFAULT '',
    base_url VARCHAR(512) NOT NULL DEFAULT '',
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 邮箱验证码
CREATE TABLE IF NOT EXISTS verify_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    code VARCHAR(10) NOT NULL,
    expires_at DATETIME NOT NULL,
    used TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 全局配置
CREATE TABLE IF NOT EXISTS config (
    cfg_key VARCHAR(100) PRIMARY KEY,
    cfg_value TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
