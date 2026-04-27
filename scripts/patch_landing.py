#!/usr/bin/env python3
with open('/root/.openclaw/workspace/docs/repo-landing/index.html', 'rb') as f:
    content = f.read()

old = b'''<!-- Quick Start Terminal -->
  <div style="background:#1a1a25;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:1.5rem;margin:2rem auto;max-width:600px;text-align:center;">
    <div style="color:#64748b;font-size:0.85rem;margin-bottom:0.75rem;">&#x5FEB;&#x901F;&#x5F00;&#x59CB;</div>
    <code style="color:#10b981;font-size:1rem;font-family:monospace;">curl -sL https://raw.githubusercontent.com/YuchenKuney/openclaw-memory-architecture-public/main/scripts/install.sh | bash</code>
  </div>'''

new = b'''<!-- Quick Start Terminal -->
  <div style="background:#1a1a25;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:1.5rem;margin:2rem auto;max-width:600px;text-align:center;">
    <div style="color:#64748b;font-size:0.85rem;margin-bottom:0.75rem;">&#x5FEB;&#x901F;&#x5F00;&#x59CB;</div>
    <div style="color:#94a3b8;font-size:0.8rem;margin-bottom:0.5rem;">&#x6D77;&#x5916;&#x7248;</div>
    <code style="color:#10b981;font-size:0.9rem;font-family:monospace;display:block;margin-bottom:1rem;">curl -sL https://raw.githubusercontent.com/YuchenKuney/openclaw-memory-architecture-public/main/scripts/install.sh | bash</code>
    <div style="color:#94a3b8;font-size:0.8rem;margin-bottom:0.5rem;">&#x56FD;&#x5185;&#x65E0;&#x68AF;&#x5B50;&#x52A0;&#x901F;&#x7248;</div>
    <code style="color:#06b6d4;font-size:0.9rem;font-family:monospace;">curl -sSL https://ghproxy.net/https://raw.githubusercontent.com/YuchenKuney/openclaw-memory-architecture-public/main/scripts/install.sh | bash</code>
  </div>'''

if old in content:
    content = content.replace(old, new)
    with open('/root/.openclaw/workspace/docs/repo-landing/index.html', 'wb') as f:
        f.write(content)
    print('Done')
else:
    print('Pattern not found')