import json
import sys

def convert_questions(input_file):
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for test in data.get("tests", []):
        formatted_string = f"Test name: {test.get("name", "noname")}\n\n"
        answer_string = f"{test.get("name", "noname")} (answers):\n"
        counter = 1
        for q in test.get("questions", []):
            question = q["question"]
            
            options = [") ".join(list(opt.items())[0]) for opt in q["options"]]
            
            answer_letter = q["answer"]
            
            options_str = "\n".join(options)
            formatted_string += f'{counter}. {question}\n\n{options_str}\n\n{"-"*80}\n\n'
            answer_string += f'{counter}. {answer_letter}\n'
            counter += 1
        formatted_string += "\n\n"
        answer_string += "\n\n\n"
        print(formatted_string)
        print(answer_string)
        print()

if __name__ == "__main__":        
    convert_questions(sys.argv[1])