"""
Maps skill names (lowercase) to Codeforces tags, Wikipedia terms,
coding test requirements, and default language for Piston execution.
"""

SKILL_CONFIG = {
    "dsa": {
        "codeforces_tags": ["implementation", "dp", "graphs", "binary search", "greedy", "sorting"],
        "wikipedia_terms": ["Data structure", "Algorithm", "Dynamic programming", "Graph theory"],
        "needs_coding_test": True,
        "language": "python",
    },
    "python": {
        "codeforces_tags": ["implementation", "strings", "math"],
        "wikipedia_terms": ["Python (programming language)", "List comprehension", "Object-oriented programming"],
        "needs_coding_test": True,
        "language": "python",
    },
    "c++": {
        "codeforces_tags": ["implementation", "data structures", "math"],
        "wikipedia_terms": ["C++", "Standard Template Library", "Object-oriented programming"],
        "needs_coding_test": True,
        "language": "cpp",
    },
    "java": {
        "codeforces_tags": ["implementation", "data structures"],
        "wikipedia_terms": ["Java (programming language)", "Java collections framework"],
        "needs_coding_test": True,
        "language": "java",
    },
    "javascript": {
        "codeforces_tags": ["implementation", "strings"],
        "wikipedia_terms": ["JavaScript", "DOM manipulation", "Asynchronous programming"],
        "needs_coding_test": True,
        "language": "js",
    },
    "machine learning": {
        "codeforces_tags": [],
        "wikipedia_terms": ["Machine learning", "Supervised learning", "Neural network", "Gradient descent"],
        "needs_coding_test": False,
        "language": "python",
    },
    "deep learning": {
        "codeforces_tags": [],
        "wikipedia_terms": ["Deep learning", "Convolutional neural network", "Backpropagation"],
        "needs_coding_test": False,
        "language": "python",
    },
    "sql": {
        "codeforces_tags": [],
        "wikipedia_terms": ["SQL", "Database normalization", "Join (SQL)", "Index (database)"],
        "needs_coding_test": False,
        "language": "python",
    },
    "oops": {
        "codeforces_tags": ["implementation"],
        "wikipedia_terms": ["Object-oriented programming", "Inheritance (OOP)", "Polymorphism", "Encapsulation"],
        "needs_coding_test": True,
        "language": "python",
    },
    "html": {
        "codeforces_tags": [],
        "wikipedia_terms": ["HTML", "HTML element", "Document Object Model"],
        "needs_coding_test": False,
        "language": "python",
    },
    "css": {
        "codeforces_tags": [],
        "wikipedia_terms": ["CSS", "CSS selector", "Responsive web design", "Flexbox"],
        "needs_coding_test": False,
        "language": "python",
    },
    "git": {
        "codeforces_tags": [],
        "wikipedia_terms": ["Git", "Version control", "Branching (version control)"],
        "needs_coding_test": False,
        "language": "python",
    },
    "linux": {
        "codeforces_tags": [],
        "wikipedia_terms": ["Linux", "Unix shell", "File system", "Process management"],
        "needs_coding_test": False,
        "language": "python",
    },
}

DEFAULT_CONFIG = {
    "codeforces_tags": ["implementation"],
    "wikipedia_terms": [],
    "needs_coding_test": False,
    "language": "python",
}


def get_skill_config(skill_name: str) -> dict:
    """Return configuration for the given skill name, falling back to DEFAULT_CONFIG."""
    normalized = skill_name.lower().strip()
    return SKILL_CONFIG.get(normalized, DEFAULT_CONFIG)
