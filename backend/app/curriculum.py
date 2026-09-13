"""Authorable curriculum seed data. Solutions are displayed, never executed by the API."""

PRIMER = [
    (
        "Variables and the values they name",
        """A program is a list of instructions. Python follows them from top to bottom. A variable gives a value a name so we can use it again.

count = 3
count = count + 1
print(count)  # 4

The equals sign assigns the right-hand value to the left-hand name. It does not ask whether two values are equal. On the second line Python reads the old count, adds one, then stores the result. Read it as ‘count becomes count plus one’.

Integers such as 3 count whole things. Floats such as 2.5 represent decimal values. Strings such as 'cat' hold text. Booleans are True or False. None means no value is present. Use == to compare equality; != means not equal. The expression 3 < 5 produces True. Division / gives a decimal; // performs floor division; % gives a remainder. For nonnegative integers, n % 2 is zero exactly when n is even.

Try on paper: x = 5, y = x, x = 9. What is y? It remains 5: assigning x later does not change the earlier integer bound to y. Check understanding: what are the type and value of 7 // 2? An integer, 3.""",
    ),
    (
        "Conditionals and loops",
        """A conditional chooses which instructions to run. Indentation, usually four spaces, tells Python which lines belong together.

score = 4
if score >= 5:
    print('ready')
elif score >= 3:
    print('practice')
else:
    print('start small')

Only the first matching branch runs. This example prints practice. Use and when both conditions must hold, or when either is enough, and not to reverse a Boolean.

A for loop visits values one at a time:
total = 0
for n in [2, 4, 6]:
    total += n

The total becomes 2, then 6, then 12. range(3) supplies 0, 1, 2: the stopping boundary is excluded. range(1, 4) supplies 1, 2, 3. A while loop repeats while its condition stays true:
n = 3
while n > 0:
    n -= 1

Every while loop needs progress toward stopping. Without the decrement, it never ends. break leaves the nearest loop; continue skips to its next turn. Before coding a loop, say what changes and why it stops. Practice: count how many numbers in [1, 6, 3, 8] exceed 4. Start count at zero and increment only inside an if; the answer is 2.""",
    ),
    (
        "Functions and tracing",
        """A function names a reusable calculation. Parameters are its inputs; return sends a result back to the caller.

def twice(value):
    return value * 2

answer = twice(4)

The caller supplies 4. Inside twice, value names 4. Returning 8 ends the call, and answer receives 8. print displays a value but does not return it. A function without an explicit return returns None.

To trace code, make a small table with columns for changing variables. Run one line at a time. Never skip a loop iteration while learning. Start with the smallest possible input, including an empty list when allowed.

def total(numbers):
    result = 0
    for number in numbers:
        result += number
    return result

For [3, 1], result is initially 0, becomes 3, then 4. For [], the loop runs zero times and returns 0. Variables created inside a function are normally local to that call. Use descriptive names; inputs such as numbers are easier to follow than unexplained letters. Check understanding: why is return result outside the loop? Returning inside would end the function after the first number.""",
    ),
    (
        "Lists, strings, tuples and slicing",
        """A list stores an ordered sequence: items = [8, 3, 5]. Python counts positions from zero, so items[0] is 8 and items[2] is 5. len(items) is 3. The final legal positive index is len(items) - 1. items[-1] accesses the last element. An index outside the list raises IndexError.

items.append(7) adds at the end. items.pop() removes and returns the last element. items[1] = 9 changes one element. Iterating ‘for value in items’ gives values; ‘for index, value in enumerate(items)’ gives both position and value.

A string is an ordered sequence of characters. 'cat'[1] is 'a'. Strings cannot be changed in place: build a new string or join a list of characters. A tuple such as (2, 5) is an ordered group whose slots also cannot be reassigned; use it for a fixed coordinate or pair.

Slicing uses sequence[start:stop:step]. The stop is excluded. [8, 3, 5, 7][1:3] gives [3, 5]. Omitting the start means the beginning; omitting the stop means the end. text[::-1] makes a reversed copy. Slicing k items takes space for k copied items; it is not free.

Be careful with aliasing: other = items names the same list, so changing other also changes items. other = items[:] makes a shallow list copy. Practice: explain why [10, 20, 30][:2] contains exactly two items. Then write a loop that prints each index beside its value.""",
    ),
    (
        "Dictionaries and sets",
        """A dictionary maps unique keys to values. Think of a labeled drawer: counts = {'a': 2, 'b': 1}. counts['a'] reads 2; counts['a'] = 3 replaces that value. Reading an absent key directly raises KeyError. counts.get('z', 0) returns 0 without adding z.

counts = {}
for letter in 'aba':
    counts[letter] = counts.get(letter, 0) + 1

The dictionary ends as {'a': 2, 'b': 1}. Use ‘key in counts’ to ask whether a key exists. ‘for key, value in counts.items()’ visits pairs. Keys must be hashable: strings, integers and suitable tuples work; lists do not.

A set stores unique values without a positional order: seen = set(). seen.add(4) records membership. Adding 4 again changes nothing. ‘4 in seen’ is True. Use a set when you only need membership; use a dictionary when you also need a count or associated value. {} creates a dictionary, not an empty set.

Dictionary and set lookup, insertion and deletion take expected constant time under ordinary hashing assumptions. A list membership scan may inspect every element. Practice: scan [3, 1, 3] while adding values to a set; the second 3 is already present. What extra information would a dictionary retain? It could retain each value's frequency or its first index.""",
    ),
]
FOUNDATIONS = """An array is a row of indexed values. In this course, Python lists provide that role. A string is a row of characters. Start every problem by identifying the input, the output, and what assumptions you may use: is the list sorted, can it be empty, and are values allowed to repeat?

A contiguous segment uses neighboring positions without gaps. In [2, 7, 1, 8], [7, 1] is contiguous; [2, 1] is a subsequence but not contiguous. Many array patterns work because a segment can be described by two boundaries.

Correctness comes before speed. First describe a straightforward solution and trace it. To compare approaches, count how work grows with input length n. One pass is O(n). Trying every pair is O(n²). Halving a sorted search interval is O(log n). O(1) extra space means a fixed number of variables, independent of n. These describe growth, not exact seconds.

An invariant is a sentence that stays true as a loop runs. ‘total is the sum of the elements already visited’ explains a summation loop. Check it before the first turn, after one turn, and when the loop ends. This gives a practical correctness argument.

Python lists allow O(1) indexing; append is amortized O(1). Removing the first item shifts later items and is O(n). Sorting takes O(n log n). Never sort unless reordering is allowed or you preserve the original information you need.

Practice trace: find the maximum of [3, 8, 2]. Set best to the first value, compare each later value, and update only if larger. State what should happen on empty input before indexing. Throughout the next five patterns, stop at each visual step and predict the next boundary movement before revealing it."""


def problem(title, statement, hints, solution, explanation):
    return dict(
        title=title,
        statement=statement,
        hints=hints,
        solution=solution,
        explanation=explanation,
    )


PATTERNS = [
    dict(
        title="Two pointers",
        explanation="""Keep two positions in a sequence and move them for a reason. For a palindrome, compare the leftmost and rightmost unchecked characters. Equal characters can be dismissed together; unequal characters prove failure. The unchecked middle shrinks until zero or one character remains. For a sorted pair sum, a sum that is too small means the left value must increase; a sum that is too large means the right value must decrease. Sorted order is the proof that discarded choices cannot work. Write down that proof before moving a pointer. Most inward scans visit each position at most once: O(n) time and O(1) extra space.""",
        walkthrough=[
            {
                "values": [1, 2, 4, 7, 11],
                "active": [0, 4],
                "caption": "Target 9. Left=1 and right=11 sum to 12. Too large: discard 11, since pairing it with any larger left value is also too large.",
            },
            {
                "values": [1, 2, 4, 7, 11],
                "active": [0, 3],
                "caption": "1 + 7 = 8. Too small: discard 1, since pairing it with anything to the left of 7 is also too small.",
            },
            {
                "values": [1, 2, 4, 7, 11],
                "active": [1, 3],
                "caption": "2 + 7 = 9. Return indices 1 and 3. Each move removed an impossible boundary.",
            },
        ],
        problems=[
            problem(
                "Read a palindrome",
                "Return True if a string reads identically forward and backward. Compare exact characters, including case and spaces. Empty text is a palindrome. Example: 'level' → True; 'cat' → False.",
                [
                    "Compare the first and last unchecked characters.",
                    "Use left=0 and right=len(text)-1; move both inward only after equality.",
                    "A mismatch returns False immediately. Reaching left>=right returns True.",
                ],
                "def is_palindrome(text):\n    left, right = 0, len(text) - 1\n    while left < right:\n        if text[left] != text[right]:\n            return False\n        left += 1\n        right -= 1\n    return True",
                "For level, l matches l, then e matches e, leaving v alone. The invariant is that all characters outside the boundaries match their mirrors. No unchecked pair remains when the loop ends. Empty and single-character strings skip the loop. O(n) time, O(1) extra space.",
            ),
            problem(
                "Find a sorted pair",
                "Given a nondecreasing list of integers and a target, return indices of one distinct pair whose values sum to the target, or None. Example: [1,2,4,7,11], 9 → (1,3).",
                [
                    "Sorted order tells you which movement can increase or decrease the sum.",
                    "Start at both ends. Too small: increment left. Too large: decrement right.",
                    "Use left < right so the same item cannot be used twice.",
                ],
                "def pair_sum(numbers, target):\n    left, right = 0, len(numbers) - 1\n    while left < right:\n        total = numbers[left] + numbers[right]\n        if total == target:\n            return left, right\n        if total < target:\n            left += 1\n        else:\n            right -= 1\n    return None",
                "For [1,2,4,7,11], discard 11 after 12, then discard 1 after 8, leaving 2+7. Each discarded endpoint cannot pair successfully with any remaining opposite endpoint. Negative numbers and duplicates work because only sorted order matters. O(n) time, O(1) space.",
            ),
            problem(
                "Compact sorted duplicates",
                "Modify a sorted list in place so its first k positions contain each distinct value once. Return k; values after k do not matter. Example: [1,1,2,2,3] → k=3 and prefix [1,2,3].",
                [
                    "One position reads each value; another marks the next place to write.",
                    "The last kept value is numbers[write-1]. Copy only when the read value differs.",
                    "Handle the empty list, then initialize write=1 and scan from index 1.",
                ],
                "def compact(numbers):\n    if not numbers:\n        return 0\n    write = 1\n    for read in range(1, len(numbers)):\n        if numbers[read] != numbers[write - 1]:\n            numbers[write] = numbers[read]\n            write += 1\n    return write",
                "The kept prefix always contains the distinct values seen so far in order. Reading 1 again does nothing; reading 2 writes at index 1; reading 3 writes at index 2. Writing never passes reading, so unvisited input is safe. O(n) time and O(1) extra space; an empty input returns zero.",
            ),
        ],
    ),
    dict(
        title="Sliding window",
        explanation="""A window is a contiguous part of a sequence between left and right boundaries. Reuse work when the boundaries move: add the entering value and remove the leaving value. A fixed-size window slides by one position. A variable-size window grows until a rule fails, then shrinks until the rule holds again. This works when you can efficiently maintain the needed state. For positive-number sum constraints, shrinking reduces the sum; with negative numbers that argument fails. For unique characters, keep a set and shrink until a duplicate leaves. A boundary that only moves forward visits at most n positions, even if a while loop sits inside a for loop.""",
        walkthrough=[
            {
                "values": [2, 1, 5, 1, 3],
                "active": [0, 1, 2],
                "caption": "Size 3: sum the first window, 2+1+5=8. Record best=8.",
            },
            {
                "values": [2, 1, 5, 1, 3],
                "active": [1, 2, 3],
                "caption": "Move right: remove 2, add 1. New sum=7. Best stays 8.",
            },
            {
                "values": [2, 1, 5, 1, 3],
                "active": [2, 3, 4],
                "caption": "Remove 1, add 3. New sum=9. Best becomes 9. We reused the previous sum.",
            },
        ],
        problems=[
            problem(
                "Best fixed-length sum",
                "Return the largest sum of k consecutive integers. Require 1 <= k <= len(numbers); raise ValueError otherwise. Example: [2,1,5,1,3], k=3 → 9. Negative numbers are allowed.",
                [
                    "Compute the first window once.",
                    "For each new right index, subtract numbers[right-k] and add numbers[right].",
                    "Initialize best to the first real sum, not zero, because all values might be negative.",
                ],
                "def best_window(numbers, k):\n    if not 1 <= k <= len(numbers):\n        raise ValueError('invalid window size')\n    total = sum(numbers[:k])\n    best = total\n    for right in range(k, len(numbers)):\n        total += numbers[right] - numbers[right - k]\n        best = max(best, total)\n    return best",
                "Window sums in the example are 8, 7 and 9. Each update replaces exactly one element, preserving the invariant that total is the current k-element sum. O(n) time. This readable initialization slice uses O(k) temporary space; summing the first k positions in a loop instead reduces extra space to O(1).",
            ),
            problem(
                "Longest unique substring",
                "Return the length of the longest contiguous substring with no repeated character. Example: 'abba' → 2; '' → 0.",
                [
                    "Keep a set for the current window.",
                    "When the next character is already present, remove characters from the left until it is absent.",
                    "After adding the new character, the length is right-left+1.",
                ],
                "def longest_unique(text):\n    seen = set()\n    left = best = 0\n    for right, char in enumerate(text):\n        while char in seen:\n            seen.remove(text[left])\n            left += 1\n        seen.add(char)\n        best = max(best, right - left + 1)\n    return best",
                "For abba, window ab reaches length 2. The second b forces removal of a and then the first b. Adding the final a gives ba, also length 2. The set always contains exactly the unique characters in the current window. Each character enters and leaves at most once: expected O(n) time and O(min(n, alphabet size)) space.",
            ),
            problem(
                "Shortest positive-sum window",
                "Given positive integers and a positive target, return the shortest contiguous length whose sum is at least target, or 0 if impossible. Example: [2,3,1,2,4,3], target=7 → 2.",
                [
                    "Grow the right boundary until the total reaches the target.",
                    "While the total is sufficient, record the length and shrink from the left.",
                    "All numbers must be positive for shrinking to reduce the total predictably.",
                ],
                "def shortest_sum(numbers, target):\n    if target <= 0 or any(x <= 0 for x in numbers):\n        raise ValueError('positive values required')\n    left = total = 0\n    best = len(numbers) + 1\n    for right, value in enumerate(numbers):\n        total += value\n        while total >= target:\n            best = min(best, right - left + 1)\n            total -= numbers[left]\n            left += 1\n    return 0 if best > len(numbers) else best",
                "After reaching 7, every valid shrink is measured before another value leaves. Eventually [4,3] gives length 2. Because all numbers are positive, a shorter valid suffix cannot be missed when shrinking. Both boundaries move forward at most n times, so O(n) time and O(1) extra space. This algorithm is not valid for arbitrary negative values.",
            ),
        ],
    ),
    dict(
        title="Prefix sum",
        explanation="""A prefix is everything before a boundary. Define prefix[0]=0 and prefix[i+1]=prefix[i]+numbers[i]. Then prefix[r]-prefix[l] is the sum of numbers[l:r], where r is excluded. The subtraction cancels the shared beginning. One O(n) preparation allows O(1) range-sum queries. The leading zero makes a range beginning at index zero use the same formula as every other range. Prefix sums use O(n) extra space. When counting target-sum subarrays, a dictionary of earlier prefix values can replace the full array: a current prefix p needs an earlier prefix p-target.""",
        walkthrough=[
            {
                "values": [0, 3, 4, 8, 10],
                "active": [0],
                "caption": "For input [3,1,4,2], build prefix [0,3,4,8,10]. Position i means the sum before input index i.",
            },
            {
                "values": [0, 3, 4, 8, 10],
                "active": [1, 4],
                "caption": "Query input indices [1,4): values 1,4,2. Read prefix[4]=10 and prefix[1]=3.",
            },
            {
                "values": [0, 3, 4, 8, 10],
                "active": [1, 4],
                "caption": "Subtract 10-3=7. The shared initial 3 cancels. No loop is needed for this query.",
            },
        ],
        problems=[
            problem(
                "Build running totals",
                "Return a prefix array beginning with zero. Example: [3,1,4] → [0,3,4,8]; [] → [0].",
                [
                    "Begin the result with [0].",
                    "The next prefix is the last prefix plus the next value.",
                    "Use append so earlier prefix values stay available.",
                ],
                "def prefixes(numbers):\n    prefix = [0]\n    for value in numbers:\n        prefix.append(prefix[-1] + value)\n    return prefix",
                "After each input value, the final prefix is the sum of all values processed. The initial zero represents processing none. There are n+1 boundaries for n values. O(n) time and O(n) space; negative numbers are handled by ordinary addition.",
            ),
            problem(
                "Answer range-sum queries",
                "Build prefix sums, then answer each half-open query (left,right) satisfying 0 <= left <= right <= n. Example: numbers=[3,1,4,2], queries=[(1,4),(0,2),(2,2)] → [7,4,0].",
                [
                    "The sum before right includes the wanted range and the earlier beginning.",
                    "Subtract the sum before left.",
                    "Validate every boundary; an empty range has the same left and right.",
                ],
                "def range_sums(numbers, queries):\n    prefix = [0]\n    for value in numbers:\n        prefix.append(prefix[-1] + value)\n    answers = []\n    for left, right in queries:\n        if not 0 <= left <= right <= len(numbers):\n            raise ValueError('invalid range')\n        answers.append(prefix[right] - prefix[left])\n    return answers",
                "For [1,4), 10-3=7. For [0,2), 4-0=4. For [2,2), subtracting the same boundary gives zero. O(n+q) time for q queries and O(n+q) output-plus-prefix space. Each individual prepared query is O(1). The original list is unchanged, and a range ending at n uses the final prefix boundary.",
            ),
            problem(
                "Count target-sum subarrays",
                "Return the number of contiguous, nonempty subarrays whose sum equals target. Integers may be negative. Example: [1,-1,1], target=1 → 3.",
                [
                    "If current prefix is p, an earlier prefix p-target begins a matching subarray.",
                    "Store how often each earlier prefix has appeared, beginning with {0:1}.",
                    "Count matches before adding the current prefix so target=0 does not count an empty subarray.",
                ],
                "def count_subarrays(numbers, target):\n    frequencies = {0: 1}\n    prefix = answer = 0\n    for value in numbers:\n        prefix += value\n        answer += frequencies.get(prefix - target, 0)\n        frequencies[prefix] = frequencies.get(prefix, 0) + 1\n    return answer",
                "Prefixes are 0,1,0,1. At the first 1 there is one earlier 0; at the final 1 there are two earlier 0s. Total 3 corresponds to the first [1], the entire list, and the final [1]. Counting frequencies preserves repeated boundaries. Expected O(n) time, O(n) space. Unlike positive sliding windows, this remains correct with negative numbers.",
            ),
        ],
    ),
    dict(
        title="Hash-map counting",
        explanation="""A hash map is Python's dictionary. Use it to retain a small fact about every distinct value you have seen: a frequency, an index, or a needed partner. Counting turns repeated scans into expected constant-time lookups. The central question is what the key means and when its value should change. For frequencies, increment after each visit. For a two-sum partner search, check for the partner before inserting the current value, so one item cannot pair with itself. Expected time is O(n); memory grows with the distinct keys, at most O(n).""",
        walkthrough=[
            {
                "values": ["a", "b", "a", "c", "a"],
                "active": [0],
                "caption": "Start with {}. Read a: missing count defaults to 0, then becomes 1. Map: {a:1}.",
            },
            {
                "values": ["a", "b", "a", "c", "a"],
                "active": [1, 2],
                "caption": "Read b, then a. Map: {a:2,b:1}. A repeated key updates its count rather than adding a second key.",
            },
            {
                "values": ["a", "b", "a", "c", "a"],
                "active": [3, 4],
                "caption": "Read c, then a. Final map: {a:3,b:1,c:1}. Every value equals the number of visits to that key.",
            },
        ],
        problems=[
            problem(
                "Count each value",
                "Return a dictionary of frequencies for a list of integers. Example: [4,2,4,4] → {4:3,2:1}; [] → {}.",
                [
                    "Create an empty dictionary.",
                    "A missing key starts at zero.",
                    "Assign counts[value] = counts.get(value,0)+1.",
                ],
                "def frequencies(numbers):\n    counts = {}\n    for value in numbers:\n        counts[value] = counts.get(value, 0) + 1\n    return counts",
                "Each visit contributes exactly one to its value's key. The three visits to 4 produce 1,2,3; the single visit to 2 produces 1. Expected O(n) time and O(u) space for u distinct values. You cannot use a set alone because it discards repeat counts.",
            ),
            problem(
                "Compare anagrams",
                "Return whether two strings contain exactly the same character frequencies. Compare exact characters. Example: 'listen','silent' → True; 'aab','abb' → False.",
                [
                    "Different lengths cannot have identical frequencies.",
                    "Count characters from the first string, then subtract for the second.",
                    "If a needed character's remaining count is zero, return False.",
                ],
                "def anagrams(first, second):\n    if len(first) != len(second):\n        return False\n    counts = {}\n    for char in first:\n        counts[char] = counts.get(char, 0) + 1\n    for char in second:\n        if counts.get(char, 0) == 0:\n            return False\n        counts[char] -= 1\n    return True",
                "For aab versus abb, counts begin a:2,b:1. Removing a and b leaves a:1,b:0, so the next b fails. Equal lengths ensure no counts remain positive after a successful full subtraction. Expected O(n) time, O(u) space. Spaces and uppercase characters are significant under this contract.",
            ),
            problem(
                "Find an unsorted pair",
                "Return indices of two distinct values summing to target, or None. Input need not be sorted. Example: [3,2,4], target=6 → (1,2); [3,3], target=6 → (0,1).",
                [
                    "The current value needs partner = target-value.",
                    "Remember an earlier index for each value in a dictionary.",
                    "Look up the partner before saving the current value so it cannot match itself.",
                ],
                "def two_sum(numbers, target):\n    seen = {}\n    for index, value in enumerate(numbers):\n        partner = target - value\n        if partner in seen:\n            return seen[partner], index\n        seen[value] = index\n    return None",
                "For [3,2,4], remember 3 at index 0 and 2 at index 1. The 4 needs 2, which is already present. For [3,3], the first 3 is saved before the second arrives, producing distinct indices. Every possible earlier partner has been retained. Expected O(n) time and O(n) space; sorting is unnecessary and would otherwise disturb indices.",
            ),
        ],
    ),
    dict(
        title="Binary search",
        explanation="""Binary search repeatedly halves a sorted candidate interval. Use the half-open interval [left,right): left is included and right is excluded. Set left=0 and right=len(numbers). Compute middle=(left+right)//2. If the middle value is below the target, all positions through middle are too small, so set left=middle+1. Otherwise keep middle as a possible answer by setting right=middle. Stop when left==right. This form finds the first position whose value is at least the target, called the lower bound. It also finds insertion positions and the first true value of a monotone predicate. The input must be sorted or the predicate must change from false to true at most once. Every step shrinks the interval; O(log n) time, O(1) extra space.""",
        walkthrough=[
            {
                "values": [1, 3, 3, 6, 9],
                "active": [0, 2, 4],
                "caption": "Find first value >=3. Interval [0,5), middle=2, value=3. Middle could be first, so move right to 2.",
            },
            {
                "values": [1, 3, 3, 6, 9],
                "active": [0, 1],
                "caption": "Interval [0,2), middle=1, value=3. Keep middle as candidate: right=1.",
            },
            {
                "values": [1, 3, 3, 6, 9],
                "active": [0],
                "caption": "Interval [0,1), middle=0, value=1. Too small: left=1. Boundaries meet at index 1, the first 3.",
            },
        ],
        problems=[
            problem(
                "Find a target",
                "Return the first target index in a sorted list, or -1 if absent. Example: [1,3,3,6], target=3 → 1; target=4 → -1.",
                [
                    "Find the first index with value >=target.",
                    "Use a half-open interval and set right=middle when the middle value is large enough.",
                    "After the loop, check the index is in bounds and its value equals target.",
                ],
                "def search(numbers, target):\n    left, right = 0, len(numbers)\n    while left < right:\n        middle = (left + right) // 2\n        if numbers[middle] < target:\n            left = middle + 1\n        else:\n            right = middle\n    if left < len(numbers) and numbers[left] == target:\n        return left\n    return -1",
                "All positions before left are too small; right bounds the first possible sufficiently large value. Keeping equality on the right side leads to the first duplicate. The final equality check distinguishes finding a target from finding its insertion point. O(log n) time, O(1) space; empty input safely returns -1.",
            ),
            problem(
                "Choose an insertion position",
                "Return the first index where target can be inserted without breaking sorted order. Insert before existing equals. Example: [1,3,5], target=4 → 2; target=8 → 3; [] → 0.",
                [
                    "An insertion position can equal len(numbers), unlike an element index.",
                    "Find the first value >=target with lower bound.",
                    "Return left directly when the boundaries meet.",
                ],
                "def insertion_index(numbers, target):\n    left, right = 0, len(numbers)\n    while left < right:\n        middle = (left + right) // 2\n        if numbers[middle] < target:\n            left = middle + 1\n        else:\n            right = middle\n    return left",
                "For target 4, values 1 and 3 are too small and 5 is large enough, so index 2 separates the two regions. If every value is smaller, the answer is n. The returned position is meaningful even for an empty list. O(log n) time and O(1) space. Actually inserting into a Python list may still cost O(n); only locating the position is logarithmic.",
            ),
            problem(
                "Integer square root",
                "For a nonnegative integer n, return the largest integer x with x*x <= n. Example: 20 → 4; 0 → 0. Do not use a square-root library.",
                [
                    "Search for the first integer whose square exceeds n, then subtract one.",
                    "The predicate x*x>n is monotone for nonnegative x.",
                    "Use interval [0,n+1); move left when middle squared is <=n.",
                ],
                "def integer_sqrt(n):\n    if n < 0:\n        raise ValueError('n must be nonnegative')\n    left, right = 0, n + 1\n    while left < right:\n        middle = (left + right) // 2\n        if middle * middle <= n:\n            left = middle + 1\n        else:\n            right = middle\n    return left - 1",
                "For 20 the first square above 20 is 5², so return 4. For 0, testing 0 moves left to 1 and returns 0. The invariant is that all integers before left satisfy the square constraint and all excluded integers at or beyond right fail it. O(log(n+1)) comparisons and O(1) auxiliary integer variables; Python's arbitrary-precision arithmetic adds bit-cost for very large n.",
            ),
        ],
    ),
]
STUBS = [
    "Stacks and queues",
    "Linked lists",
    "Recursion from first principles",
    "Trees and traversal",
    "Heaps and priority queues",
    "Graphs and traversal",
    "Backtracking",
    "Dynamic programming",
]
