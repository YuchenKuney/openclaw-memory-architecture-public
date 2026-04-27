#!/usr/bin/env python3
with open('/root/.openclaw/workspace/docs/repo-landing/index.html', 'rb') as f:
    content = f.read()

old = b'</div>\n\n  <!-- GitHub Stats'
new = b'''</div>

  <!-- Quick Start Terminal -->
  <div style="background:#1a1a25;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:1.5rem;margin:2rem auto;max-width:600px;text-align:center;">
    <div style="color:#64748b;font-size:0.85rem;margin-bottom:0.75rem;">&#x5FEB;&#x901F;&#x5F00;&#x59CB;</div>
    <code style="color:#10b981;font-size:1rem;font-family:monospace;">curl -sL https://raw.githubusercontent.com/YuchenKuney/openclaw-memory-architecture-public/main/scripts/install.sh | bash</code>
  </div>

  <!-- GitHub Stats'''

if old in content:
    content = content.replace(old, new)
    with open('/root/.openclaw/workspace/docs/repo-landing/index.html', 'wb') as f:
        f.write(content)
    print('Done')
else:
    print('Pattern not found')
    lines = content.split(b'\n')
    for i, line in enumerate(lines[376:386], 377):
        print(f'{i}: {line[:80]}')