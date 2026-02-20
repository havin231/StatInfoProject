import re

translations = {
    "Information Coming Soon": "زانیارییەکان بەمزووانە بەردەست دەبن",
    "The administration is currently updating this page.": "بەڕێوەبەرایەتی لە ئێستادا ئەم پەڕەیە نوێ دەکاتەوە.",
    "Return Home": "گەڕانەوە بۆ سەرەتا",
    "Edit This Page (Admin Only)": "دەستکاریکردنی ئەم پەڕەیە (تەنها بەڕێوەبەر)",
    "Select the best answer for each question below.": "باشترین وەڵام بۆ هەر پرسیارێکی خوارەوە هەڵبژێرە.",
    "No Questions Found": "هیچ پرسیارێک نەدۆزرایەوە",
    "There are no questions assigned to this exam/lecture yet.": "هێشتا هیچ پرسیارێک بۆ ئەم تاقیکردنەوەیە/وانەیە دانەنراوە.",
    "Go Back": "گەڕانەوە",
    "Submit Exam": "ناردنی تاقیکردنەوە",
    "Submitting Exam...": "لە ناردنی تاقیکردنەوەدایە...",
    "Connecting to server...": "پەیوەندیکردن بە سێرڤەرەوە...",
    "DO NOT REFRESH THE PAGE": "پەڕەکە نوێ مەکەرەوە",
    "Are you sure you want to submit your answers?": "دڵنیایت دەتەوێت وەڵامەکانت بنێریت؟",
    "Server verified. Uploading answers...": "سێرڤەر پشتڕاستکرایەوە. لە بارکردنی وەڵامەکان...",
    "Waking up server (this may take 20s)...": "بەئاگاهێنانەوەی سێرڤەر (لەوانەیە ٢٠ چرکە بخایەنێت)...",
    "Secure Staff Portal": "پۆرتاڵی پارێزراوی کارمەندان",
    "Email Address": "ناونیشانی ئیمەیڵ",
    "Password": "تێپەڕوشە",
    "Login as Student": "چوونەژوورەوە وەک خوێندکار",
    "Back to Subject": "گەڕانەوە بۆ بابەت",
    "Take Lecture Quiz": "تاقیکردنەوەی وانە بکە",
    "Learning Resources": "سەرچاوەکانی فێربوون",
    "Read in Kurdish / وەرگێڕان": "خوێندنەوە بە کوردی / وەرگێڕان",
    "Read in English": "خوێندنەوە بە ئینگلیزی",
    "System Initialization": "دەستپێکردنی سیستەم",
    "Welcome to SchoolLMS. Please create the primary": "بەخێربێیت بۆ SchoolLMS. تکایە ئەکاونتی سەرەکی",
    "Headmaster": "بەڕێوەبەر",
    "account to begin.": "دروست بکە بۆ دەستپێکردن.",
    "This is a one-time setup process.": "ئەمە پڕۆسەیەکی ڕێکخستنی یەکجارەکییە.",
    "Academic Performance": "ئاستی ئەکادیمی",
    "Real-time analytics and class metrics.": "شیکاری ڕاستەوخۆ و پێوەرەکانی پۆل.",
    "Total Exams": "کۆی تاقیکردنەوەکان",
    "Global Average": "ڕێژەی گشتی",
    "Total Students": "کۆی خوێندکاران",
    "Subject Performance": "ئاستی بابەت",
    "Pass to Fail Ratio": "ڕێژەی دەرچوون بۆ کەوتن",
    "Detailed Breakdown": "وردەکارییەکان",
    "Subject": "بابەت",
    "Average Score": "تێکڕای نمرە",
    "No exam data available yet.": "هێشتا داتای تاقیکردنەوە بەردەست نییە.",
    "Enter your unique access code to continue.": "کۆدی چوونەژوورەوەی تایبەتیت بنووسە بۆ بەردەوامبوون.",
    "Access Code": "کۆدی چوونەژوورەوە",
    "Register New Student": "تۆمارکردنی خوێندکاری نوێ",
    "Login as Teacher": "چوونەژوورەوە وەک مامۆستا",
    "Student Registration": "تۆماری خوێندکار",
    "Create your account to access exams and study materials.": "هەژمارەکەت دروستبکە بۆ چوونە ناو تاقیکردنەوەکان و سەرچاوەکانی خوێندن.",
    "Already have an account?": "پێشتر هەژمارت هەیە؟",
    "Login\n                            here": "لێرە چوونەژوورەوە بکە",
    "Site Content Manager": "بەڕێوەبەری ناوەڕۆکی ماڵپەڕ",
    "View Live Page": "بینینی پەڕەی ڕاستەوخۆ",
    "Pro Tip:": "ئامۆژگاری:",
    "Click the \"Source\" button\n                    in the toolbar to write raw HTML/CSS.": "کرتە لە دوگمەی \"Source\" بکە بۆ نووسینی HTML/CSS ی ڕاستەوخۆ.",
    "Cancel": "هەڵوەشاندنەوە",
    "Edit Student:": "دەستکاریکردنی خوێندکار:",
    "Full Name": "ناوی تەواو",
    "Edit Staff Profile": "دەستکاریکردنی پرۆفایلی کارمەند",
    "Grant System Administrator Access": "پێدانی دەسەڵاتی بەڕێوەبەری سیستەم",
    "Warning:": "ئاگاداری:",
    "Admins have full control, including deleting\n                            users and content.": "بەڕێوەبەرەکان دەسەڵاتی تەواویان هەیە، لەوانە سڕینەوەی بەکارهێنەران و ناوەڕۆک.",
    "Review Data Import": "پێداچوونەوەی داتای هاوردەکراو",
    "Please verify the data below before saving to the database.": "تکایە دڵنیابەرەوە لەم داتایانەی خوارەوە پێش پاشەکەوتکردن.",
    "Rows Found": "ڕیز دۆزرایەوە",
    "Batch\n                            Settings:": "ڕێکخستنەکانی کۆمەڵە:",
    "Assign to Lecture:": "دیاریکردن بۆ وانە:",
    "(None - General Subject Exam)": "(هیچ - تاقیکردنەوەی گشتی بابەت)",
    "Mark all as Kurdish (RTL)": "هەمووی وەک کوردی (ڕاست بۆ چەپ) دیاریبکە",
    "Preview Mode Only": "تەنها دۆخی پێشاندانی پێشوەختە",
    "This data is held in memory. It will": "ئەم داتایانە لە بیرگەدا هەڵگیراون. هەرگیز",
    "not": "نا",
    "be\n                                saved until you click\n                                \"Confirm Import\".": "پاشەکەوت ناکرێن تا کرتە نەکەیت لە \"پشتڕاستکردنەوەی هاوردەکردن\".",
    "Generated Access Code": "کۆدی چوونەژوورەوەی دروستکراو",
    "Question": "پرسیار",
    "Options (A / B / C / D)": "هەڵبژاردنەکان (A / B / C / D)",
    "Answer": "وەڵام",
    "Cancel & Discard": "هەڵوەشاندنەوە و فڕێدان",
    "Confirm Import": "پشتڕاستکردنەوەی هاوردەکردن",
    "Member of Group:": "ئەندامی گروپ:",
    "Browse Subjects": "گەڕان بەناو بابەتەکاندا",
    "Quick Actions": "کردارە خێراکان",
    "My Settings": "ڕێکخستنەکانم",
    "Sign Out": "چوونە دەرەوە",
    "Action Required": "پێویست بە کردار دەکات",
    "Please add your email address to secure your account and receive\n                        notifications.": "تکایە ناونیشانی ئیمەیڵەکەت زیاد بکە بۆ پاراستنی ئەکاونتەکەت و وەرگرتنی ئاگادارینامە.",
    "Add Email": "زیادکردنی ئیمەیڵ",
    "Exams Completed": "تاقیکردنەوە تەواوکراوەکان",
    "Subject Mastery": "شارەزایی بابەت",
    "Average Performance per Course": "تێکڕای ئاست لە هەر خولێکدا",
    "Excellent": "زۆر باشە",
    "Passing": "دەرچوون",
    "Needs Review": "پێویستی بە پێداچوونەوەیە",
    "No exams taken yet. Start a subject to track your mastery!": "هێشتا هیچ تاقیکردنەوەیەکت نەکردووە. دەستپێبکە بە بابەتێک بۆ بینینی ئاستت!",
    "Recent Exam Activity": "دوایین چالاکییەکانی تاقیکردنەوە",
    "Date Submitted": "بەرواری ناردن",
    "Score": "نمرە",
    "Actions": "کردارەکان",
    "Review": "پێداچوونەوە",
    "Your exam history is currently empty.": "مێژووی تاقیکردنەوەکانت لە ئێستادا بەتاڵە.",
    "Exam Results:": "ئەنجامەکانی تاقیکردنەوە:",
    "Taken on": "لە بەرواری",
    "Final Score": "نمرەی کۆتایی",
    "Return to Dashboard": "گەڕانەوە بۆ داشبۆرد",
    "The correct answer was": "وەڵامی ڕاست بریتی بوو لە",
    "Account Settings": "ڕێکخستنەکانی هەژمار",
    "Action Required:": "پێویست بە کردار دەکات:",
    "Please add your email address to secure your\n                    account.": "تکایە ناونیشانی ئیمەیڵەکەت زیاد بکە بۆ پاراستنی ئەکاونتەکەت.",
    "Personal Information": "زانیاری کەسی",
    "We will use this for important notifications and\n                            account recovery.": "ئەمە بەکاردەهێنین بۆ ئاگادارینامە گرنگەکان و گەڕاندنەوەی ئەکاونت.",
    "Appearance": "ڕواڵەت",
    "Academic Glass": "ڕوانگەی ئەکادیمی",
    "Cyber Command": "فەرماندەیی ئەلیکترۆنی",
    "Security": "ئاسایش",
    "My Access Code": "کۆدی چوونەژوورەوەم",
    "If you change this, you will need to use the new code to login next time.": "ئەگەر ئەمە بگۆڕیت، پێویستە لە جاری داهاتوودا کۆدە نوێیەکە بەکاربهێنیت بۆ چوونەژوورەوە.",
    "Access Code:": "کۆدی چوونەژوورەوە:",
    "Export Detailed Log": "هەناردەکردنی تۆماری ورد",
    "Back to Analytics": "گەڕانەوە بۆ شیکارییەکان",
    "Taken on:": "لە بەرواری:",
    "Score:": "نمرە:",
    "Selection": "هەڵبژاردن",
    "Correct Ans": "وەڵامی ڕاست",
    "Result": "ئەنجام",
    "Correct": "ڕاستە",
    "Wrong": "هەڵەیە",
    "Answer log for this exam is\n                            unavailable.": "تۆماری وەڵامەکان بۆ ئەم تاقیکردنەوەیە بەردەست نییە.",
    "No Exam History Found": "مێژووی تاقیکردنەوە نەدۆزرایەوە",
    "This student has not yet completed any exams.": "ئەم خوێندکارە هێشتا هیچ تاقیکردنەوەیەکی ئەنجام نەداوە."
}

with open('app/translations/ku/LC_MESSAGES/messages.po', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
current_msgid = ""
is_collecting_msgid = False
i = 0

while i < len(lines):
    line = lines[i]
    
    if line.startswith('msgid "'):
        val = line[7:-2] # Strip msgid " and "\n
        if val == "":
            is_collecting_msgid = True
            current_msgid = ""
        else:
            is_collecting_msgid = False
            current_msgid = val.replace('\\n', '\n')
            
        new_lines.append(line)
        i += 1
        continue
        
    if is_collecting_msgid and line.startswith('"'):
        val = line[1:-2]
        current_msgid += val.replace('\\n', '\n')
        new_lines.append(line)
        i += 1
        continue
        
    if line.startswith('msgstr '):
        is_collecting_msgid = False
        
        # Check if fuzzy
        if len(new_lines) >= 2 and '#, fuzzy' in new_lines[-2]:
            new_lines.pop(-2)
            
        if current_msgid in translations:
            tr = translations[current_msgid]
            if '\n' in tr:
                new_lines.append('msgstr ""\n')
                for part in tr.split('\n'):
                    new_lines.append(f'"{part}\\n"\n')
                # Remove last \\n
                new_lines[-1] = new_lines[-1].replace('\\n"', '"')
            else:
                new_lines.append(f'msgstr "{tr}"\n')
        else:
            new_lines.append(line)
        i += 1
        continue
        
    new_lines.append(line)
    i += 1
    
with open('app/translations/ku/LC_MESSAGES/messages.po', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Translation replacements applied.")
