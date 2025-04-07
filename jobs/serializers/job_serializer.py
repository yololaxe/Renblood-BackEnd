import json
from rest_framework import serializers
from jobs.models.job import Job

class JobSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='_id')
    skills = serializers.SerializerMethodField()
    mastery = serializers.SerializerMethodField()
    inter_choice = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ['id', 'name', 'skills', 'inter_choice', 'mastery']

    def get_skills(self, obj):
        raw_skills = obj.skills
        if isinstance(raw_skills, str):
            try:
                parsed = json.loads(raw_skills)
            except:
                parsed = {}
        else:
            parsed = raw_skills

        # 🔐 S'assurer que choice_1 à choice_4 existent
        for i in range(1, 5):
            key = f"choice_{i}"
            if key not in parsed:
                parsed[key] = []

        return parsed


    def get_mastery(self, obj):
        return self._parse_json_field(obj.mastery)

    def get_inter_choice(self, obj):
        return self._parse_json_field(obj.inter_choice)

    def _parse_json_field(self, field):
        if isinstance(field, str):
            try:
                return json.loads(field)
            except Exception:
                return field  # fallback
        return field  # already parsed
