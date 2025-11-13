import re

with open('admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the send_to_khazenly_bulk method, get_urls, send_to_khazenly_view, and export_to_excel_for_khazenly methods
# Pattern: from @admin.action for send_to_khazenly_bulk through export_to_excel_for_khazenly return None
pattern = r'\n    @admin\.action\(description=\'Send selected pills to Khazenly.*?return None\n    \n'
content = re.sub(pattern, '\n', content, flags=re.DOTALL)

with open('admin.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed khazenly bulk action and export methods")
