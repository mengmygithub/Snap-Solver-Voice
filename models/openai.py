import os
from typing import Generator, Optional, List, Dict, Any
from contextlib import contextmanager
from openai import OpenAI
from .base import BaseModel

class OpenAIModel(BaseModel):
    def __init__(self, api_key, temperature=0.7, system_prompt=None, language=None, api_base_url=None, model_identifier=None):
        super().__init__(api_key, temperature, system_prompt, language)
        self.api_base_url = api_base_url
        self.model_identifier = model_identifier or "gpt-4o-2024-11-20"
        
    def get_default_system_prompt(self) -> str:
        return """You are an expert at analyzing questions and providing detailed solutions. When presented with an image of a question:
1. First read and understand the question carefully
2. Break down the key components of the question
3. Provide a clear, step-by-step solution
4. If relevant, explain any concepts or theories involved
5. If there are multiple approaches, explain the most efficient one first"""

    def get_model_identifier(self) -> str:
        return self.model_identifier

    @contextmanager
    def _proxy_env(self, proxies: Optional[dict]):
        original_env = {
            'http_proxy': os.environ.get('http_proxy'),
            'https_proxy': os.environ.get('https_proxy')
        }
        try:
            if proxies:
                if 'http' in proxies:
                    os.environ['http_proxy'] = proxies['http']
                if 'https' in proxies:
                    os.environ['https_proxy'] = proxies['https']
            yield
        finally:
            for key, value in original_env.items():
                if value is None:
                    if key in os.environ:
                        del os.environ[key]
                else:
                    os.environ[key] = value

    def _create_client(self) -> OpenAI:
        if self.api_base_url:
            return OpenAI(api_key=self.api_key, base_url=self.api_base_url)
        return OpenAI(api_key=self.api_key)

    def _get_max_tokens(self) -> int:
        try:
            return int(getattr(self, 'max_tokens', 4000) or 4000)
        except Exception:
            return 4000

    def _yield_error(self, e: Exception) -> Generator[dict, None, None]:
        yield {"status": "error", "error": str(e)}

    def _stream_chat_completions(self, client: OpenAI, messages: List[Dict[str, Any]]) -> Generator[dict, None, None]:
        kwargs = {
            "model": self.get_model_identifier(),
            "messages": messages,
            "stream": True,
            "max_tokens": self._get_max_tokens()
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        response = client.chat.completions.create(**kwargs)

        response_buffer = ""
        for chunk in response:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                response_buffer += content
                if len(content) >= 10 or content.endswith(('.', '!', '?', '。', '！', '？', '\n')):
                    yield {"status": "streaming", "content": response_buffer}

        if response_buffer:
            yield {"status": "streaming", "content": response_buffer}
        yield {"status": "completed", "content": response_buffer}

    def _stream_responses(self, client: OpenAI, *, input_payload: Any, instructions: Optional[str]) -> Generator[dict, None, None]:
        kwargs = {
            "model": self.get_model_identifier(),
            "stream": True
        }
        if instructions:
            kwargs["instructions"] = instructions
        kwargs["input"] = input_payload

        stream = client.responses.create(**kwargs)

        response_buffer = ""
        for event in stream:
            event_type = getattr(event, "type", None)
            if event_type is None and isinstance(event, dict):
                event_type = event.get("type")

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta is None and isinstance(event, dict):
                    delta = event.get("delta")
                if delta:
                    response_buffer += delta
                    if len(delta) >= 10 or str(delta).endswith(('.', '!', '?', '。', '！', '？', '\n')):
                        yield {"status": "streaming", "content": response_buffer}

        if response_buffer:
            yield {"status": "streaming", "content": response_buffer}
        yield {"status": "completed", "content": response_buffer}

    def analyze_text(self, text: str, proxies: dict = None) -> Generator[dict, None, None]:
        """Stream GPT-4o's response for text analysis"""
        try:
            yield {"status": "started", "content": ""}

            with self._proxy_env(proxies):
                client = self._create_client()

                if hasattr(client, "responses"):
                    input_payload = [
                        {
                            "role": "user",
                            "content": [{"type": "input_text", "text": text}]
                        }
                    ]
                    yield from self._stream_responses(client, input_payload=input_payload, instructions=self.system_prompt)
                else:
                    messages = [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": text}
                    ]
                    yield from self._stream_chat_completions(client, messages)

        except Exception as e:
            yield from self._yield_error(e)

    def analyze_image(self, image_data: str, proxies: dict = None) -> Generator[dict, None, None]:
        """Stream GPT-4o's response for image analysis"""
        try:
            yield {"status": "started", "content": ""}
            with self._proxy_env(proxies):
                client = self._create_client()

                if hasattr(client, "responses"):
                    input_payload = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_data}"},
                                {"type": "input_text", "text": "Please analyze this image and provide a detailed solution."}
                            ]
                        }
                    ]
                    yield from self._stream_responses(client, input_payload=input_payload, instructions=self.system_prompt)
                else:
                    messages = [
                        {"role": "system", "content": self.system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                                {"type": "text", "text": "Please analyze this image and provide a detailed solution."}
                            ]
                        }
                    ]
                    yield from self._stream_chat_completions(client, messages)

        except Exception as e:
            yield from self._yield_error(e)
