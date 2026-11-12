/**
 * One explanation of how fees apply, used by the page, the empty table and the assign dialog.
 * On the school's server a student owes a fee structure only once it's assigned to them (nothing
 * is assigned automatically, not even on admission); a concession lowers one student's amount
 * for one structure. The sample data applies class structures automatically.
 */
export function feeAssignmentCopy(live: boolean) {
  return live
    ? {
        page: "A student owes a fee structure only after it's assigned to them here. Assign each class's standard fee structure to its students, assign optional fees (like transport) to the students who take them, and record concessions to lower what a student owes.",
        section: "Fee assignments",
        button: "Assign fee structure",
        empty: "No fee structures are assigned yet. Students owe nothing until a fee structure is assigned to them.",
        dialogTitle: "Assign a fee structure to a student",
        dialogDescription: "The student will owe this structure's installments, less any concession. Use it for the class's standard fees and for optional fees such as transport.",
      }
    : {
        page: "Students pay their class's fee structures automatically. Add extra fees (like transport) for individual students, and record discounts or exemptions.",
        section: "Extra fees for individual students",
        button: "Assign to a student",
        empty: "No individual assignments. Class fee structures already apply to every student in the class.",
        dialogTitle: "Assign fees to a student",
        dialogDescription: "For fees outside the student's class structure, like transport.",
      };
}
