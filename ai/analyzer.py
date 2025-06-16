import asyncio
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import openai
from loguru import logger

from config.settings import settings, extract_addresses_fast, has_urgent_keywords, is_valid_solana_address


@dataclass
class AnalysisResult:
    """Result of post analysis"""
    has_contract: bool
    addresses: List[str]
    confidence: float
    signals: List[str]
    urgency: str  # 'low', 'medium', 'high'
    analysis_time_ms: float
    method: str  # 'fast', 'ai', 'hybrid'
    context: str = ""


class UltraFastAnalyzer:
    """Ultra-fast analysis system with optional AI confirmation"""

    def __init__(self):
        self.ai_client = None
        self.analysis_cache = {}  # Cache for AI results
        self.setup_ai()

    def setup_ai(self):
        """Setup AI client if configured"""
        if settings.ai.use_ai_confirmation and settings.ai.openai_api_key:
            self.ai_client = openai.AsyncOpenAI(api_key=settings.ai.openai_api_key)
            logger.info("AI analyzer initialized")
        else:
            logger.info("AI analyzer disabled - using fast analysis only")

    async def analyze_post(self, content: str, platform: str, author: str = "", url: str = "") -> AnalysisResult:
        """
        Main analysis method - prioritizes speed
        1. Fast regex analysis (immediate)
        2. AI analysis (background, optional)
        """
        start_time = time.time()

        # STEP 1: ULTRA-FAST ANALYSIS (always runs)
        fast_result = self.fast_analysis(content)

        # If fast analysis finds addresses, return immediately for trading speed
        if fast_result.has_contract and fast_result.confidence > 0.6:
            fast_result.analysis_time_ms = (time.time() - start_time) * 1000

            # Start AI analysis in background (don't wait for it)
            if self.ai_client and settings.ai.use_ai_confirmation:
                asyncio.create_task(self.background_ai_analysis(content, platform, author))

            logger.info(f"FAST CONTRACT DETECTED: {fast_result.addresses} in {fast_result.analysis_time_ms:.1f}ms")
            return fast_result

        # STEP 2: AI CONFIRMATION (only if fast analysis is uncertain)
        if self.ai_client and settings.ai.use_ai_confirmation:
            try:
                ai_result = await asyncio.wait_for(
                    self.ai_analysis(content),
                    timeout=settings.ai.ai_timeout
                )

                # Combine fast + AI results
                combined_result = self.combine_results(fast_result, ai_result)
                combined_result.analysis_time_ms = (time.time() - start_time) * 1000
                combined_result.method = 'hybrid'

                return combined_result

            except asyncio.TimeoutError:
                logger.warning(f"AI analysis timed out after {settings.ai.ai_timeout}s")
                fast_result.analysis_time_ms = (time.time() - start_time) * 1000
                return fast_result
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                fast_result.analysis_time_ms = (time.time() - start_time) * 1000
                return fast_result

        # Return fast result if AI is disabled
        fast_result.analysis_time_ms = (time.time() - start_time) * 1000
        return fast_result

    def fast_analysis(self, content: str) -> AnalysisResult:
        """Ultra-fast regex-based analysis"""
        # Extract addresses using compiled regex patterns
        addresses = extract_addresses_fast(content)

        # Check for urgent keywords
        has_urgent = has_urgent_keywords(content)

        # Calculate confidence
        confidence = 0.0
        signals = []

        if addresses:
            confidence += 0.7  # High confidence for valid addresses
            signals.append("contract_address_found")

        if has_urgent:
            confidence += 0.2
            signals.append("urgent_keywords")

        # Check for specific token mentions
        content_lower = content.lower()
        if '$mori' in content_lower:
            confidence += 0.3
            signals.append("mori_token_mentioned")

        if any(word in content_lower for word in ['launch', 'live', 'contract', 'ca:']):
            confidence += 0.1
            signals.append("launch_keywords")

        urgency = 'high' if has_urgent else 'medium' if addresses else 'low'

        return AnalysisResult(
            has_contract=len(addresses) > 0,
            addresses=addresses,
            confidence=min(confidence, 1.0),
            signals=signals,
            urgency=urgency,
            analysis_time_ms=0,  # Will be set by caller
            method='fast',
            context=f"Fast analysis found {len(addresses)} addresses"
        )

    async def ai_analysis(self, content: str) -> AnalysisResult:
        """AI-based analysis for complex cases"""
        # Check cache first
        content_hash = hash(content)
        if settings.ai.cache_ai_results and content_hash in self.analysis_cache:
            cached_result = self.analysis_cache[content_hash]
            logger.debug("Using cached AI result")
            return cached_result

        prompt = f"""
Analyze this crypto post for token contracts. Respond with JSON only:

"{content}"

{{
  "has_contract": boolean,
  "addresses": ["addr1", "addr2"],
  "signals": ["signal1", "signal2"],
  "urgency": "low|medium|high",
  "confidence": 0.0-1.0,
  "context": "brief explanation"
}}

Look for Solana addresses (32-44 chars, Base58). Be fast and accurate.
"""

        try:
            response = await self.ai_client.chat.completions.create(
                model=settings.ai.model,
                messages=[
                    {"role": "system",
                     "content": "You are a fast crypto trading signal analyzer. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.ai.max_tokens,
                temperature=settings.ai.temperature
            )

            ai_response = response.choices[0].message.content.strip()

            # Parse JSON response
            import json
            try:
                parsed = json.loads(ai_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    raise ValueError("Invalid JSON response from AI")

            # Validate addresses
            valid_addresses = [addr for addr in parsed.get('addresses', []) if is_valid_solana_address(addr)]

            result = AnalysisResult(
                has_contract=bool(parsed.get('has_contract', False)),
                addresses=valid_addresses,
                confidence=float(parsed.get('confidence', 0.0)),
                signals=parsed.get('signals', []),
                urgency=parsed.get('urgency', 'low'),
                analysis_time_ms=0,
                method='ai',
                context=parsed.get('context', 'AI analysis')
            )

            # Cache the result
            if settings.ai.cache_ai_results:
                self.analysis_cache[content_hash] = result

                # Limit cache size
                if len(self.analysis_cache) > 1000:
                    # Remove oldest entries
                    oldest_keys = list(self.analysis_cache.keys())[:100]
                    for key in oldest_keys:
                        del self.analysis_cache[key]

            return result

        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return AnalysisResult(
                has_contract=False,
                addresses=[],
                confidence=0.0,
                signals=[],
                urgency='low',
                analysis_time_ms=0,
                method='ai_error',
                context=f"AI analysis failed: {str(e)}"
            )

    async def background_ai_analysis(self, content: str, platform: str, author: str):
        """Run AI analysis in background for learning/improvement"""
        try:
            result = await self.ai_analysis(content)
            logger.debug(f"Background AI analysis completed for {platform}:{author}")
            # Could store results for model improvement or additional validation
        except Exception as e:
            logger.debug(f"Background AI analysis failed: {e}")

    def combine_results(self, fast_result: AnalysisResult, ai_result: AnalysisResult) -> AnalysisResult:
        """Combine fast and AI analysis results"""
        # Merge addresses
        all_addresses = list(set(fast_result.addresses + ai_result.addresses))

        # Take higher confidence
        combined_confidence = max(fast_result.confidence, ai_result.confidence)

        # Merge signals
        all_signals = list(set(fast_result.signals + ai_result.signals))

        # Take higher urgency
        urgency_levels = {'low': 0, 'medium': 1, 'high': 2}
        fast_urgency = urgency_levels.get(fast_result.urgency, 0)
        ai_urgency = urgency_levels.get(ai_result.urgency, 0)
        combined_urgency = ['low', 'medium', 'high'][max(fast_urgency, ai_urgency)]

        return AnalysisResult(
            has_contract=len(all_addresses) > 0,
            addresses=all_addresses,
            confidence=combined_confidence,
            signals=all_signals,
            urgency=combined_urgency,
            analysis_time_ms=0,  # Will be set by caller
            method='hybrid',
            context=f"Combined: {len(all_addresses)} addresses, confidence {combined_confidence:.2f}"
        )

    async def health_check(self) -> bool:
        """Check if analyzer is working"""
        try:
            # Test fast analysis
            test_result = self.fast_analysis("Test contract: 11111111111111111111111111111114")
            if not test_result.has_contract:
                return False

            # Test AI if enabled
            if self.ai_client:
                test_ai = await asyncio.wait_for(
                    self.ai_analysis("Test message"),
                    timeout=5.0
                )
                logger.info("AI analyzer health check passed")

            return True

        except Exception as e:
            logger.error(f"Analyzer health check failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get analyzer statistics"""
        return {
            "cache_size": len(self.analysis_cache),
            "ai_enabled": self.ai_client is not None,
            "fast_analysis_enabled": True
        }


# Global analyzer instance
analyzer = UltraFastAnalyzer()