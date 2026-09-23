"""Conservative local rules: source preservation and relevant questions."""
import unittest


class LocalFallbackTests(unittest.TestCase):
    def setUp(self):
        from app import ai_service
        self.service = ai_service
        self.rich = (
            "Проблема: Операторы вручную разбирают обращения.\n"
            "Данные: CSV с 200 обезличенными обращениями.\n"
            "Результат: Прототип классификатора обращений.\n"
            "Критерии: Не менее 8 верных категорий на 10 примерах.\n"
            "Ограничения: За 3 дня, без внешних сервисов.\n"
            "Пользователи: Операторы поддержки.\n"
            "Контакт: Руководитель, Telegram @demo_contact."
        )

    def test_weak_and_rich_drafts_have_different_relevant_questions(self):
        weak = self.service._fallback_analyze("Хотим улучшить обслуживание")
        rich = self.service._fallback_analyze(self.rich)
        self.assertEqual(weak["covered_fields"], [])
        self.assertEqual(len(weak["questions"]), 5)
        self.assertEqual(set(rich["covered_fields"]), set(self.service.FIELD_HINTS))
        self.assertEqual(rich["missing_fields"], [])
        self.assertEqual(len(rich["questions"]), 3)
        self.assertNotEqual(weak["questions"], rich["questions"])
        self.assertTrue(all("Вы указали" in question["question"] for question in rich["questions"]))

    def test_missing_questions_prioritized_and_lists_disjoint(self):
        result = self.service._fallback_analyze("Проблема: Клиенты долго ждут.\nДанные: CSV с заказами.")
        self.assertEqual(result["covered_fields"], ["context_need", "data_sources"])
        self.assertEqual({q["field"] for q in result["questions"]}, set(result["missing_fields"]))
        self.assertFalse(set(result["covered_fields"]) & set(result["missing_fields"]))

    def test_assembly_preserves_each_source_and_new_answer_without_invention(self):
        original = self.service._extract_draft_fields(self.rich)
        answer = "В CSV есть столбцы text и category."
        result = self.service._fallback_assemble(self.rich, [{"field": "data_sources", "answer": answer}])["fields"]
        for key, snippet in original.items():
            self.assertIn(snippet, result[key])
            self.assertIn(snippet, self.rich)
        self.assertEqual(result["data_sources"], original["data_sources"] + "\n" + answer)
        self.assertEqual(result["constraints"], "За 3 дня, без внешних сервисов.")

    def test_unknown_values_are_not_coverage_or_invented_values(self):
        text = "Данные: нет данных\nРезультат: не указано\nКонтакт: не знаю\nПользователи: -"
        result = self.service._fallback_analyze(text)
        self.assertEqual(result["covered_fields"], [])
        fields = self.service._fallback_assemble(text, [{"field": "users", "answer": "не знаю"}])["fields"]
        self.assertTrue(all(value == "" for value in fields.values()))

    def test_concrete_unlabelled_cues_copy_original_sentences(self):
        sentences = ["Сейчас заявки разбирают вручную.", "У нас есть CSV с обращениями.",
                     "Нужен прототип для операторов.", "Срок 3 дня.", "Связь через Telegram."]
        fields = self.service._extract_draft_fields(" ".join(sentences))
        self.assertEqual(fields["context_need"], sentences[0])
        self.assertEqual(fields["data_sources"], sentences[1])
        self.assertEqual(fields["expected_result"], sentences[2])
        self.assertEqual(fields["users"], sentences[2])
        self.assertEqual(fields["constraints"], sentences[3])
        self.assertEqual(fields["contact_format"], sentences[4])
        self.assertEqual(fields["success_criteria"], "")
