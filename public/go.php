<?php
/**
 * クリック計測リダイレクタ（常駐不要・LiteSpeed/PHPがリクエスト毎に実行）。
 *
 * /go/<link_id>?src=web|x で呼ばれ、links から dest_url を引き、clicks に記録して302。
 * オープンリダイレクト対策: dest_url は登録済み(links)のもののみ＋許可ドメインに限定。
 */
declare(strict_types=1);

$dbPath = __DIR__ . '/../data/app.db';      // public_html配下の構成に合わせ調整
$fallback = 'https://www.rakuten.co.jp/';

$linkId = isset($_GET['id']) ? preg_replace('/[^a-f0-9]/', '', (string)$_GET['id']) : '';
$src = isset($_GET['src']) ? substr(preg_replace('/[^a-z]/', '', (string)$_GET['src']), 0, 8) : 'web';

$allowedHosts = [
    'rakuten.co.jp', 'hb.afl.rakuten.co.jp', 'a.r10.to',
    'af.moshimo.com', 'amazon.co.jp', 'amzn.to',
    'shopping.yahoo.co.jp',
];

function host_allowed(string $url, array $allowed): bool {
    $host = strtolower((string)parse_url($url, PHP_URL_HOST));
    if ($host === '') return false;
    foreach ($allowed as $h) {
        if ($host === $h || str_ends_with($host, '.' . $h)) return true;
    }
    return false;
}

$dest = $fallback;
if ($linkId !== '' && is_readable($dbPath)) {
    try {
        $pdo = new PDO('sqlite:' . $dbPath, null, null, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        ]);
        $stmt = $pdo->prepare('SELECT dest_url FROM links WHERE link_id = :id');
        $stmt->execute([':id' => $linkId]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        if ($row && host_allowed($row['dest_url'], $allowedHosts)) {
            $dest = $row['dest_url'];
            $ua = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 255);
            $ins = $pdo->prepare(
                'INSERT INTO clicks (link_id, src, ua, ts) VALUES (:id, :src, :ua, :ts)'
            );
            $ins->execute([
                ':id' => $linkId, ':src' => $src, ':ua' => $ua,
                ':ts' => gmdate('c'),
            ]);
        }
    } catch (Throwable $e) {
        // 記録に失敗してもリダイレクトは必ず行う（ユーザー体験優先）
        error_log('go.php: ' . $e->getMessage());
    }
}

header('Location: ' . $dest, true, 302);
echo 'Redirecting...';
