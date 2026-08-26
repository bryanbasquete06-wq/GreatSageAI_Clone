# -*- coding: utf-8 -*-
"""Notificacoes nativas do Windows."""
import logging
import platform
import subprocess

logger = logging.getLogger("greatsage.notifications")

def notify(title: str, message: str, duration: int = 5) -> bool:
    """Envia notificacao nativa do Windows via PowerShell."""
    try:
        if platform.system() == "Windows":
            ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{title}</text>
            <text>{message}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Great Sage AI").Show($toast)
'''
            subprocess.run(["powershell", "-Command", ps_script],
                          capture_output=True, timeout=10)
            return True
    except Exception as e:
        logger.debug(f"Notificacao via PowerShell falhou: {e}")

    logger.info(f"[NOTIFY] {title}: {message}")
    return False
