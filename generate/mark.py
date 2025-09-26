import random
import pandas as pd

# Subjects
subjects = ["Math", "Physics", "Chemistry", "English", "CS"]

# Roll numbers 101–178
roll_numbers = list(range(101, 179))

# Create dictionary for marks
marks_data = {"Roll No": roll_numbers}

# Generate random marks (out of 100) for each subject
for subject in subjects:
    marks_data[subject] = [random.randint(30, 100) for _ in roll_numbers]

# Convert to DataFrame
df_marks = pd.DataFrame(marks_data)

# Display preview
print("Marks per Subject (Preview):\n")
print(df_marks.head(10))

# Save to CSV
df_marks.to_csv("marks.csv", index=False)
print("\n✅ Marks saved to 'marks.csv'")
