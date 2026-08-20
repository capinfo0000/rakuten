<?php
/**
 * メール登録エンドポイント（リスト化導線）。
 * 値下げ/セール速報の購読者を subscribers テーブルに保存＝自分の資産を蓄積。
 * 常駐不要（LiteSpeed/PHPがリクエスト毎に実行）。
 */
declare(strict_types=1);

$dbPath = __DIR__ . '/../data/app.db';
$thanks = '/?subscribed=1';

$email = isset($_POST['email']) ? trim((string)$_POST['email']) : '';
$source = isset($_POST['source']) ? substr(preg_replace('/[^a-z]/', '', (string)$_POST['source']), 0, 8) : 'web';

if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    header('Location: /?error=email', true, 302);
    echo 'invalid email';
    exit;
}

try {
    $pdo = new PDO('sqlite:' . $dbPath, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('CREATE TABLE IF NOT EXISTS subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, '
             . 'email TEXT UNIQUE, source TEXT, created_at TEXT)');
    $stmt = $pdo->prepare('INSERT OR IGNORE INTO subscribers (email, source, created_at) '
                        . 'VALUES (:email, :source, :ts)');
    $stmt->execute([':email' => $email, ':source' => $source, ':ts' => gmdate('c')]);
} catch (Throwable $e) {
    error_log('subscribe.php: ' . $e->getMessage());
}

header('Location: ' . $thanks, true, 302);
echo 'Thanks!';
