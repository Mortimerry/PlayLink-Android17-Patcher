"""Exact input releases and verification references for the PlayLink patcher."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    title: str
    package: str
    aspect_parent: str
    aspect_ratio: float
    activity_aspect_attribute: bool
    dex_hash: str
    manifest_hash: str

    @property
    def activity(self):
        return self.package + ".UnityPlayerActivityWithPS4Discovery"


PROFILES = {
    "b8382fe09858b5eabf953322ecefd0485db67c15c8e283ef083b89fc0e15892d": Profile(
        "Knowledge is Power 1.5", "com.playstation.knowledge", "activity", 2.1, False,
        "549cd6d391941b0b0d8a8689e7a7018b2cb5a3aa058750d829d4d4e37f69b414",
        "3260ccb14ad984a150e7fef2469d18f3c57e5a540a98b869c9c546e7422b5dd3",
    ),
    "877c21a0baf6e88d526acff64683746259f359a432434291b1cea5c8f629a60e": Profile(
        "Knowledge is Power: Decades 1.4", "com.playstation.kipdecades", "application", 2.1, False,
        "b5895ac51a6a5f56a858e42086af0900fb9a3c164738829957bb2c80f106f926",
        "521700c7f2e84b2f993bc7830f661ab3a22e44066cb47fadb40d283a5ce1c071",
    ),
    "6bf13282cd189e3a960e56fff0f8f5acd1e4460d831d0c21ee022c55889379d5": Profile(
        "That's You! 1.6", "com.playstation.iwyk", "activity", 2.4, True,
        "56d5a65c77ae19a428e5df7d7961d354b68d4287f5739a775d64e3759f2c2837",
        "6f4dc07aea2e016b9af073ad0916dc20d1e6b9264704b84f2ed549e950ba2335",
    ),
}
