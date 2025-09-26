import random
import pandas as pd

# List of subjects
subjects = ["Math", "Physics", "Chemistry", "English", "CS"]

# List of roll numbers
roll_numbers = list(range(101, 179)) 
# Create empty dictionary to store attendance
attendance_data = {"Roll No": roll_numbers}

# Generate random attendance % for each subject
for subject in subjects:
    attendance_data[subject] = [random.randint(50, 100) for _ in roll_numbers]

# Convert to DataFrame
df = pd.DataFrame(attendance_data)

# Display attendance table
print("Attendance per Subject:\n")
print(df)

# Save to CSV (optional)
df.to_csv("attendance.csv", index=False)
print("\nAttendance saved to 'attendance.csv'")
