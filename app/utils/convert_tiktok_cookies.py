import json

INPUT_FILE = "tiktok_cookies.json"
OUTPUT_FILE = "tiktok_cookies_netscape.txt"


def json_cookies_to_netscape(json_path: str, output_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    if not isinstance(cookies, list):
        raise ValueError(
            "File JSON harus berupa ARRAY/list cookie. "
            "Kalau isinya object tunggal atau format lain, cek ulang hasil export-nya."
        )

    lines = ["# Netscape HTTP Cookie File"]
    skipped = 0

    for c in cookies:
        name = c.get("name", "")
        value = c.get("value", "")
        if not name:
            skipped += 1
            continue

        domain = c.get("domain", "") or ".tiktok.com"
        if not domain.startswith("."):
            domain = "." + domain.lstrip(".")
        domain_specified = "TRUE" if domain.startswith(".") else "FALSE"

        path = c.get("path", "/") or "/"
        secure = "TRUE" if c.get("secure", False) else "FALSE"


        raw_expiry = c.get("expirationDate") or c.get("expiry") or c.get("expires")
        if raw_expiry:
            try:
                expiry = int(float(raw_expiry))
            except (TypeError, ValueError):
                expiry = 2147483647
        else:
            # Session cookie (tidak ada expiry) -> pakai far-future timestamp
            expiry = 2147483647

        lines.append(f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✅ Selesai! {len(lines) - 1} cookie berhasil dikonversi ({skipped} dilewati karena tanpa nama).")
    print(f"📄 Hasil disimpan di: {output_path}")
    print("👉 Buka file itu, copy SELURUH isinya, paste ke TIKTOK_COOKIES_CONTENT di Railway.")


if __name__ == "__main__":
    json_cookies_to_netscape(INPUT_FILE, OUTPUT_FILE)