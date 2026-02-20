import os
import glob

template_dir = 'app/templates'
html_files = glob.glob(os.path.join(template_dir, '**', '*.html'), recursive=True)

for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace escaped single quotes in Jinja translations
    patched_content = content.replace("_({\\'", "_('").replace("\\'})", "')").replace("_(\\'", "_('").replace("\\')", "')")
    
    if patched_content != content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(patched_content)
        print(f"Fixed {file}")
