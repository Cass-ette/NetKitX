"""Terms of Service content for NetKitX."""

TERMS_VERSION = "1.0"

TERMS_CONTENT = {
    "zh-CN": """# NetKitX 服务条款

## 1. 授权测试声明
本平台仅限用于已获得合法授权的安全测试场景。用户必须在使用任何扫描或测试功能前，确保已获得目标系统所有者的书面授权。

## 2. 法律合规
用户承诺遵守《中华人民共和国网络安全法》《数据安全法》《个人信息保护法》及其他相关法律法规。未经授权对他人计算机信息系统进行渗透测试属于违法行为。

## 3. 用户责任
- 用户对使用本平台进行的所有操作承担全部法律责任
- 用户必须仅对已授权的目标进行安全测试
- 用户不得利用本平台从事任何违法活动
- 用户应妥善保管账户凭证，防止未授权访问

## 4. 禁止行为
- 对未授权目标发起任何形式的扫描或攻击
- 利用本平台进行拒绝服务攻击
- 窃取、篡改或破坏他人数据
- 传播恶意软件或病毒
- 任何违反中国法律法规的行为

## 5. 免责声明
NetKitX 作为安全测试工具平台，不对用户的具体使用行为承担责任。因用户违反本条款或相关法律而产生的一切后果，由用户自行承担。

## 6. 条款变更
我们保留随时修改本条款的权利。条款变更后继续使用本平台即表示接受修改后的条款。
""",
    "en": """# NetKitX Terms of Service

## 1. Authorized Testing Declaration
This platform is intended solely for legally authorized security testing scenarios. Users must ensure they have obtained written authorization from the target system owner before using any scanning or testing features.

## 2. Legal Compliance
Users agree to comply with all applicable laws and regulations, including but not limited to the Cybersecurity Law of the People's Republic of China, the Data Security Law, and the Personal Information Protection Law. Unauthorized penetration testing of computer systems is illegal.

## 3. User Responsibility
- Users bear full legal responsibility for all operations performed using this platform
- Users must only conduct security tests on authorized targets
- Users must not use this platform for any illegal activities
- Users should safeguard their account credentials to prevent unauthorized access

## 4. Prohibited Activities
- Scanning or attacking unauthorized targets in any form
- Conducting denial-of-service attacks using this platform
- Stealing, tampering with, or destroying others' data
- Distributing malware or viruses
- Any activity that violates applicable laws and regulations

## 5. Disclaimer
NetKitX, as a security testing tool platform, is not responsible for users' specific usage. All consequences arising from users' violation of these terms or relevant laws shall be borne by the users themselves.

## 6. Changes to Terms
We reserve the right to modify these terms at any time. Continued use of this platform after changes constitutes acceptance of the modified terms.
""",
}


def get_terms(lang: str = "en") -> dict:
    """Return terms content for the given language."""
    if lang.startswith("zh"):
        content = TERMS_CONTENT["zh-CN"]
    else:
        content = TERMS_CONTENT["en"]
    return {"version": TERMS_VERSION, "content": content}
