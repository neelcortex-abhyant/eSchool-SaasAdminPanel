/** What each module's note says when it runs on sample data or on the server. */
export const OPS_LIVE_NOTE = {
  grading: "Connected to the school's server. Report cards are built from processed offline exam results; generate them per exam to store the grades on the server.",
  fees:
    "Connected to the school's server. A student owes fees only for the structures assigned to them, so assign each class's structure to its students. The server doesn't support installments or late fees yet, and doesn't take online payments here.",
  transport:
    "Connected to the school's server. The server keeps a vehicle's name, registration and seats (no driver, helper or type yet), and stops and student transport can be added or removed but not edited.",
};

export const OPS_SAMPLE_NOTE =
  "This page uses sample data saved only in this browser. Set NEXT_PUBLIC_OPS_API_MODE=live to use the school's server.";
