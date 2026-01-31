import re
import csv
import zipfile
import io
import ast

SQL_FILE = 'all_my_data.sql'
OUTPUT_ZIP = 'emergency_restore.zip'

# 1. DEFINE HEADERS (Must match flask routes.py export function)
HEADERS = {
    'user': ['ID', 'Name', 'Email', 'Password_Hash', 'Is_Admin'],
    'subject': ['ID', 'Name', 'Slug', 'Description', 'Teacher_ID'],
    'student': ['ID', 'Full_Name', 'Access_Code', 'Group_ID'],
    'page': ['ID', 'Subject_ID', 'Title', 'Content_EN', 'Content_KU'],
    'resource': ['ID', 'Page_ID', 'Title', 'Link'],
    'question': ['ID', 'Subject_ID', 'Page_ID', 'Question_Text', 'Option_A', 'Option_B', 'Option_C', 'Option_D', 'Correct', 'Is_Kurdish'],
    'exam_result': ['ID', 'Student_ID', 'Subject_ID', 'Score', 'Date_Submitted'],
    'student_answer': ['ID', 'Student_ID', 'Question_ID', 'Exam_ID', 'Selected_Option', 'Is_Correct'],
    'system_command': ['Title', 'Command', 'Description'],
    'site_info': ['Key', 'Title', 'Content']
}

# 2. STORAGE
data_store = {k: [] for k in HEADERS.keys()}

def parse_sql_values(values_str):
    """
    Robust State-Machine Parser for SQL INSERT VALUES.
    Handles escaped quotes (\\') and HTML content correctly.
    """
    # FINAL ATTEMPT: Strict Character State Machine
    # This is the only robust way to handle ")," inside strings.
    
    final_rows = []
    
    current_row = []
    current_val_chars = []
    
    in_string = False
    escape_next = False
    in_row_scope = False
    
    # We iterate through the raw string
    for char in values_str:
        if in_row_scope:
            if in_string:
                # Inside a quoted string '...'
                if escape_next:
                    current_val_chars.append(char)
                    escape_next = False
                elif char == '\\':
                    escape_next = True
                elif char == "'":
                    in_string = False # Closing quote
                else:
                    current_val_chars.append(char)
            else:
                # Inside a row (...) but NOT in a string
                if char == "'":
                    in_string = True
                elif char == ',':
                    # Field separator
                    # Flush current value
                    val = "".join(current_val_chars).strip()
                    current_row.append(val)
                    current_val_chars = []
                elif char == ')':
                    # End of Row
                    # Flush last value
                    val = "".join(current_val_chars).strip()
                    current_row.append(val)
                    
                    # Process the row we just finished
                    processed_row = []
                    for v in current_row:
                        if v == 'NULL': processed_row.append(None)
                        elif v.upper() == 'TRUE': processed_row.append(True)
                        elif v.upper() == 'FALSE': processed_row.append(False)
                        elif v.isdigit(): processed_row.append(int(v))
                        else: processed_row.append(v)
                    
                    final_rows.append(processed_row)
                    
                    # Reset
                    current_row = []
                    current_val_chars = []
                    in_row_scope = False
                elif char == '(':
                    # This shouldn't happen right after a previous (
                    # unless nested? SQL doesn't really nest tuples here.
                    pass
                else:
                    # Just characters between commas (numbers, NULL, etc)
                    # or spaces
                    current_val_chars.append(char)
        else:
            # Looking for start of a row
            if char == '(':
                in_row_scope = True
                current_row = []
                current_val_chars = []
                
    return final_rows

def main():
    print(">>> 1. Reading SQL Dump Line-By-Line...")
    
    resource_id_counter = 1
    
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith("INSERT INTO"):
                continue
                
            # Parse Table Name
            # Format: INSERT INTO `table_name` VALUES ...
            match = re.match(r"INSERT INTO `(\w+)` VALUES (.*);", line)
            if not match:
                # Maybe it doesn't end with ; or distinct spacing?
                # Try relaxed match
                match = re.search(r"INSERT INTO `(\w+)` VALUES (.*)", line)
            
            if not match:
                print(f"    [!] Skipped malformed INSERT line: {line[:50]}...")
                continue
                
            table = match.group(1)
            values_str = match.group(2)
            
            if table not in HEADERS:
                continue

            print(f"    Processing {table}...")
            # Detect truncation from previous regex issue confirmation
            if table == 'page':
                 print(f"    [DEBUG] Page string length: {len(values_str)}")
            
            rows = parse_sql_values(values_str)
            print(f"    [DEBUG] Extracted {len(rows)} rows for {table}")
            
            # STORE DATA
            for row in rows:
                try:
                    if table == 'user':
                        data_store['user'].append([row[0], row[1], row[2], row[3], row[4]])

                    elif table == 'subject':
                        data_store['subject'].append([row[0], row[1], row[2], row[3], row[4]])

                    elif table == 'student':
                        data_store['student'].append([row[0], row[1], row[2], row[3]])

                    elif table == 'page':
                        # SQL: id, title, content, content_ku, resource_link, subject_id
                        # CSV: ID, Subject_ID, Title, Content_EN, Content_KU
                        data_store['page'].append([row[0], row[5], row[1], row[2], row[3]])
                        
                        # MIGRATION: Extract resource_link if it exists
                        if len(row) > 4 and row[4]: 
                            data_store['resource'].append([
                                resource_id_counter,
                                row[0], # Page ID
                                "Lecture Resource", 
                                row[4]
                            ])
                            resource_id_counter += 1

                    elif table == 'question':
                        is_k = "True" if row[9] else "False"
                        pid = row[8] if row[8] is not None else ""
                        data_store['question'].append([
                            row[0], row[7], pid, row[1], row[2], row[3], row[4], row[5], row[6], is_k
                        ])

                    elif table == 'exam_result':
                        data_store['exam_result'].append([row[0], row[3], row[4], row[1], row[2]])

                    elif table == 'student_answer':
                        is_cor = "True" if row[5] else "False"
                        data_store['student_answer'].append([row[0], row[1], row[2], row[3], row[4], is_cor])

                    elif table == 'system_command':
                        data_store['system_command'].append([row[1], row[2], row[3]])
                    
                    elif table == 'site_info':
                        data_store['site_info'].append([row[1], row[2], row[3]])
                        
                except IndexError as ie:
                    print(f"    [!] Error mapping row for {table}: {ie}")
                    continue

    print(">>> 2. Creating ZIP Archive...")
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        file_map = {
            'user': '1_users.csv',
            'subject': '2_subjects.csv',
            'student': '3_students.csv',
            'page': '4_pages.csv',
            'resource': '5_resources.csv',
            'question': '6_questions.csv',
            'exam_result': '7_results.csv',
            'student_answer': '8_answers.csv',
            'system_command': '9_commands.csv',
            'site_info': '10_siteinfo.csv'
        }

        for key, filename in file_map.items():
            s = io.StringIO()
            s.write('\ufeff') # BOM
            w = csv.writer(s, quoting=csv.QUOTE_ALL)
            w.writerow(HEADERS[key])
            w.writerows(data_store[key])
            zf.writestr(filename, s.getvalue())
            print(f"    Added {filename} ({len(data_store[key])} rows)")

    print(f"\nSUCCESS: Created {OUTPUT_ZIP}")

if __name__ == '__main__':
    main()
