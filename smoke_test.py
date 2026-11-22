"""Test the model adapter *without* creating/connecting a Telegram bot."""
import argparse
from tutor import CodexBackend, OllamaBackend, MockBackend, OpenAIAPIBackend, Tutor, EngineError


def main():
    p = argparse.ArgumentParser(description='Offline/CLI smoke test for tutor backends')
    p.add_argument('--backend', choices=['mock','codex','ollama','openai_api'],default='mock')
    p.add_argument('--image', help='Optional JPG/PNG photo of an assignment or solution')
    p.add_argument('--model', default='', help='Optional Codex or Ollama model name')
    args = p.parse_args()
    from dotenv import load_dotenv
    from pathlib import Path
    import os
    load_dotenv(Path(__file__).resolve().parent / '.env')
    backend = (OpenAIAPIBackend(api_key=os.getenv('OPENAI_API_KEY', ''), model=args.model or os.getenv('API_MODEL', 'gpt-4.1-mini')) if args.backend == 'openai_api'
               else CodexBackend(model=args.model) if args.backend == 'codex'
               else OllamaBackend(model=args.model or 'gemma3:4b') if args.backend == 'ollama'
               else MockBackend())
    task = {'title': 'Учебная задача: 3x + 7 = 22. Не показывай готового решения.'}
    try:
        result = Tutor(backend).respond(task, [], 'Я не знаю, с чего начать. Объясни принцип?',
                                        student_images=[args.image] if args.image else [])
    except EngineError as exc:
        p.exit(2, 'MODEL ERROR: '+str(exc)+'\n')
    print('Tutor reply:',result.reply)
    print('Mode:',args.backend,'; flag:',result.flag,'; mastery:',result.mastery)
    print('Parent note:',result.parent_note)
    print('IMPORTANT: this smoke test does not prove a model cannot be bypassed.')


if __name__=='__main__':
    main()
