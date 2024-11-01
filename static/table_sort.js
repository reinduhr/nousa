// This creates an object called sortDirections with two properties: mainTable and archiveTable.
// Each property is an array of booleans ([true, true, true]), where each boolean represents the sort direction 
// for a specific column in that table (true for ascending, false for descending).
// mainTable and archiveTable correspond to table IDs in your HTML, and each true/false value determines how each column in the table is sorted.
let sortDirections = { mainTable: [true, true, true], archiveTable: [true, true, true] };

// This defines the sortTable function, which sorts a specified table by a specified column.
function sortTable(columnIndex, tableId, isDate = false) {
    // Finds the table element in the HTML by its id (either mainTable or archiveTable based on the tableId parameter) and assigns it to table.
    const table = document.getElementById(tableId);
    // This selects the <tbody> section of the table, where rows are listed, and assigns it to tbody.
    const tbody = table.querySelector("tbody");
    // Creates an array of rows in the <tbody>. Using Array.from() converts the rows into a real array, enabling sorting.
    const rows = Array.from(tbody.rows);
    // Looks up the current sort direction (ascending or descending) for the specified column of the specified table.
    // direction will be true for ascending or false for descending.
    const direction = sortDirections[tableId][columnIndex];
    
    // rows.sort is called to sort the rows based on the values in the specified column.
    // The sort function receives two rows, a and b, and compares their cells at columnIndex to determine order.
    rows.sort((a, b) => {
        // These lines extract and trim the text content from the specified column (columnIndex) of each row.
        let cellA = a.cells[columnIndex].textContent.trim();
        let cellB = b.cells[columnIndex].textContent.trim();

        // If isDate is true, the function converts cellA and cellB to Date objects for proper date sorting.
        if (isDate) {
            cellA = new Date(cellA);
            cellB = new Date(cellB);
        // Checks if cellA and cellB are numbers. If they are, parseFloat converts them to numbers for proper sorting.
        } else if (!isNaN(cellA) && !isNaN(cellB)) {
            cellA = parseFloat(cellA);
            cellB = parseFloat(cellB);
        }

        // If direction is true (ascending), return 1 sorts a after b, and return -1 does the reverse.
        // If direction is false (descending), these returns are swapped.
        if (cellA > cellB) return direction ? 1 : -1;
        if (cellA < cellB) return direction ? -1 : 1;
        return 0;
    });

    // After sorting, this re-adds each row back to the <tbody> in the new order, which visually reorders them on the page.
    rows.forEach(row => tbody.appendChild(row));

    // This toggles the sorting direction for the next time you sort the same column. If it was ascending, it switches to descending, and vice versa.
    sortDirections[tableId][columnIndex] = !direction;
}