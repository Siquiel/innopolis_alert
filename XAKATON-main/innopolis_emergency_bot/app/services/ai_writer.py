from __future__ import annotations

import asyncio
import logging
import textwrap

logger = logging.getLogger(__name__)


class AiWriter:
    def __init__(self, api_key: str | None, model: str, groq_api_key: str | None = None):
        self.api_key = api_key
        self.model = model
        self.groq_api_key = groq_api_key
        self.groq_client = None
        self.gemini_client = None

        # Groq — основной провайдер
        if groq_api_key:
            try:
                from groq import Groq  # type: ignore
                self.groq_client = Groq(api_key=groq_api_key)
                logger.info("AiWriter: Groq client initialized")
            except Exception:
                logger.exception("Failed to initialize Groq client")

        # Gemini — запасной провайдер
        if api_key and not self.groq_client:
            try:
                from google import genai  # type: ignore
                self.gemini_client = genai.Client(api_key=api_key)
                logger.info("AiWriter: Gemini client initialized")
            except Exception:
                logger.exception("Failed to initialize Google GenAI client")

    def _build_prompt(self, title: str, text: str, emergency_type: str | None, danger_level: str | None) -> str:
        return textwrap.dedent(
            f"""
            Ты редактор официальных сообщений локальной системы оповещения Иннополиса.
            Твоя задача: превратить черновик в конкретное, полезное и спокойное сообщение для жителей.

            Пиши как в официальном городском канале оповещения.

            Обязательные требования:
            - не выдумывай факты, адреса, время, источники и последствия;
            - в первых строках обязательно ясно укажи, ЧТО произошло или какая угроза есть;
            - дальше дай только практические инструкции: что делать в здании, на улице, чего не делать;
            - стиль официальный, уверенный, без воды и без эмоционального нагнетания;
            - короткие абзацы, списки только когда они реально нужны;
            - если в черновике не хватает данных, не придумывай их, а аккуратно формулируй общо;
            - не добавляй фразы про ИИ, редактуру или черновик;
            - итог должен быть готов к публикации в Telegram;
            - используй эмодзи умеренно: максимум 1-2 в начале сообщения.

            Предпочтительная структура:
            1. Короткий заголовок/первая строка с сутью угрозы.
            2. Один абзац: что за ЧС или угроза.
            3. Чёткие действия для жителей.
            4. В конце: просьба сохранять спокойствие и номер 112, если это уместно.

            Формат похож на такие оповещения:
            - «Внимание. Есть угроза ...»
            - «Если вы в здании: ...»
            - «Если вы на улице: ...»
            - «Не подходите к ... / не публикуйте ...»

            Тип ЧС: {emergency_type or 'не указан'}
            Подуровень опасности: {danger_level or 'не указан'}
            Внутренний заголовок шаблона: {title}
            Черновик:
            {text}

            Верни только финальный текст сообщения для публикации.
            """
        ).strip()

    async def improve_dispatch(self, title: str, text: str, emergency_type: str | None = None, danger_level: str | None = None) -> str:
        prompt = self._build_prompt(title, text, emergency_type, danger_level)

        # Groq (основной)
        if self.groq_client:
            try:
                response = await asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    temperature=0.4,
                )
                generated = response.choices[0].message.content or ""
                return generated.strip() or self._fallback(title, text, emergency_type, danger_level)
            except Exception:
                logger.exception("Groq generation failed")

        # Gemini (запасной)
        if self.gemini_client:
            try:
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model=self.model,
                    contents=prompt,
                )
                generated = getattr(response, "text", "") or ""
                return generated.strip() or self._fallback(title, text, emergency_type, danger_level)
            except Exception:
                logger.exception("Gemini generation failed")

        return self._fallback(title, text, emergency_type, danger_level)

    @staticmethod
    def _fallback(title: str, text: str, emergency_type: str | None = None, danger_level: str | None = None) -> str:
        head = []
        if emergency_type:
            head.append(f"Тип ЧС: {emergency_type}")
        if danger_level:
            head.append(f"Уровень: {danger_level}")
        intro = "\n".join(head)
        body = text.strip()
        parts = [p for p in [f"<b>{title.strip()}</b>" if title.strip() else "", intro, body] if p]
        return "\n\n".join(parts)
