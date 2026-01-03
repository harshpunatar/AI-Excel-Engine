import pandas as pd
from faker import Faker
import random

fake = Faker()

division_names = ['Sales', 'R&D', 'Human Resources', 'Marketing', 'Accounting', 'Legal', 'Logistics']
num_divs = len(division_names)

#Column wise generate
div_ids = [200 + i for i in range(num_divs)]
budgets = [random.randint(450000, 2500000) for _ in range(num_divs)]
locations = [fake.city() for _ in range(num_divs)]

df_div = pd.DataFrame({
    "DivID": div_ids,
    "DivisionName": division_names,
    "AnnualBudget": budgets,
    "Headquarters": locations
})

#Structured Data
NUM_STAFF = 1000

staff_ids = fake.unique.random_elements(elements=range(10000, 99999), length=NUM_STAFF)
names = [fake.name() for _ in range(NUM_STAFF)]
ages = [random.randint(21, 58) for _ in range(NUM_STAFF)]
genders = random.choices(['Male', 'Female'], k=NUM_STAFF)
salaries = [random.randint(35000, 195000) for _ in range(NUM_STAFF)]
join_dates = [fake.date_between(start_date='-6y', end_date='today') for _ in range(NUM_STAFF)]
ratings = [round(random.uniform(1.0, 10.0), 1) for _ in range(NUM_STAFF)]
cities = [fake.city() for _ in range(NUM_STAFF)]
emails = [fake.email() for _ in range(NUM_STAFF)]

assigned_div_ids = random.choices(div_ids, k=NUM_STAFF)

df_staff = pd.DataFrame({
    "StaffID": staff_ids,
    "FullName": names,
    "Age": ages,
    "Gender": genders,
    "DivID": assigned_div_ids,  
    "AnnualSalary": salaries,
    "DateOfJoining": join_dates,
    "PerformanceRating": ratings,
    "HomeCity": cities,
    "ContactEmail": emails
})

#Unstructured Data
real_comments = [
    "Excellent performance this quarter, consistently met all deadlines.",
    "Needs to improve on communication skills during team meetings.",
    "Outstanding leadership shown in the recent project delivery.",
    "Technically strong but struggles with documentation.",
    "Great team player, always willing to help others.",
    "Productivity has dropped slightly compared to last year.",
    "Innovative problem solver, brought great ideas to the table.",
    "Attendance has been inconsistent, needs to be addressed.",
    "Delivered high-quality code with minimal bugs.",
    "Client feedback was very positive regarding their recent interaction.",
    "Struggles to adapt to new tools and technologies.",
    "Consistently exceeds expectations in all assigned tasks.",
    "Needs to be more proactive in identifying potential risks.",
    "Great attitude and brings positive energy to the team.",
    "Project management skills need some refinement."
]

eval_ids = [f"EVAL-{1000+i}" for i in range(NUM_STAFF)]

linked_staff_ids = random.choices(staff_ids, k=NUM_STAFF) 

texts = [random.choice(real_comments) for _ in range(NUM_STAFF)]

channels = random.choices(['Internal Portal', 'Manager Review', 'Anonymous Survey', 'Exit Interview'], k=NUM_STAFF)

dates = [fake.date_between(start_date='-1y', end_date='today') for _ in range(NUM_STAFF)]

df_eval = pd.DataFrame({
    "EvaluationID": eval_ids,
    "StaffID": linked_staff_ids,
    "Comments": texts,
    "SubmissionChannel": channels,
    "Date": dates
})

output_filename = "dataset.xlsx"

with pd.ExcelWriter(output_filename) as writer:
    df_staff.to_excel(writer, sheet_name='Staff', index=False)
    df_div.to_excel(writer, sheet_name='Divisions', index=False)
    df_eval.to_excel(writer, sheet_name='Evaluations', index=False)

print(":)")